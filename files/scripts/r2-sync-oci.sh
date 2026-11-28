#!/usr/bin/env bash
set -euo pipefail

# Kushagra OS Zero-Egress OCI Mirror Sync (Cloudflare R2)
# Usage: r2-sync-oci.sh <image-ref>
# Example: r2-sync-oci.sh ghcr.io/sgunjan2302-hash/kushagra-os:44
# Cleanly skips (exit 0) if R2 credentials are unset/empty.

if [ "$#" -lt 1 ] || [ -z "${1:-}" ]; then
    echo "Usage: $0 <oci-image-ref>" >&2
    exit 1
fi

RAW_REF="$1"
IMAGE_REF="${RAW_REF#docker://}"

# Cleanly skip when Cloudflare R2 credentials are not configured
if [ -z "${R2_ACCOUNT_ID:-}" ] || [ -z "${R2_BUCKET:-}" ] || [ -z "${AWS_ACCESS_KEY_ID:-}" ] || [ -z "${AWS_SECRET_ACCESS_KEY:-}" ]; then
    echo "[SKIP] Cloudflare R2 credentials not configured (R2_ACCOUNT_ID, R2_BUCKET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY); skipping R2 OCI sync for ${IMAGE_REF}."
    exit 0
fi

for cmd in skopeo jq aws; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "[FAIL] Required tool '$cmd' not found on PATH." >&2
        exit 1
    fi
done

# Derive repository name (e.g. kushagra-os, kushagra-os-dx) from full image ref
REF_NO_DIGEST="${IMAGE_REF%%@*}"
LAST_SEG="${REF_NO_DIGEST##*/}"
REPO_NAME="${LAST_SEG%%:*}"

if [ -z "$REPO_NAME" ] || [[ "$REPO_NAME" == *".."* ]] || [[ "$REPO_NAME" == *"/"* ]]; then
    echo "[FAIL] Could not derive valid repository name from image reference '${IMAGE_REF}'." >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COSIGN_PUB="${COSIGN_PUB:-}"
if [ -z "$COSIGN_PUB" ]; then
    if [ -f "cosign.pub" ]; then
        COSIGN_PUB="cosign.pub"
    elif [ -f "${REPO_ROOT}/cosign.pub" ]; then
        COSIGN_PUB="${REPO_ROOT}/cosign.pub"
    fi
fi

TMP_DIR="$(mktemp -d)"
cleanup() {
    rm -rf -- "$TMP_DIR"
}
trap cleanup EXIT

if command -v cosign >/dev/null 2>&1; then
    if [ -n "$COSIGN_PUB" ] && [ -f "$COSIGN_PUB" ]; then
        echo "==> Verifying Cosign signature for ${IMAGE_REF} with ${COSIGN_PUB}..."
        cosign verify --key "$COSIGN_PUB" "$IMAGE_REF"
    else
        echo "[FAIL] cosign is available, but cosign.pub could not be located." >&2
        exit 1
    fi
else
    echo "[WARN] cosign CLI not installed; skipping signature verification for ${IMAGE_REF}."
fi

OCI_DIR="${TMP_DIR}/oci"
echo "==> Exporting ${IMAGE_REF} to temporary OCI layout (${OCI_DIR})..."
skopeo copy "docker://${IMAGE_REF}" "oci:${OCI_DIR}"

if [ ! -f "${OCI_DIR}/oci-layout" ] || [ ! -f "${OCI_DIR}/index.json" ]; then
    echo "[FAIL] Invalid OCI layout exported to ${OCI_DIR} (missing oci-layout or index.json)." >&2
    exit 1
fi

RAW_OCI="$(skopeo inspect --raw "oci:${OCI_DIR}")"
LAYER_COUNT="$(printf '%s' "$RAW_OCI" | jq -r '(.layers // []) | length')"
if [ -z "$LAYER_COUNT" ] || [ "$LAYER_COUNT" = "null" ] || [ "$LAYER_COUNT" -eq 0 ]; then
    AMD64_DIGEST="$(printf '%s' "$RAW_OCI" | jq -r '.manifests[]? | select(.platform.architecture=="amd64" and .platform.os=="linux") | .digest' | head -n 1)"
    if [ -n "$AMD64_DIGEST" ] && [ "$AMD64_DIGEST" != "null" ]; then
        BLOB_FILE="${OCI_DIR}/blobs/sha256/${AMD64_DIGEST#sha256:}"
        if [ -f "$BLOB_FILE" ]; then
            LAYER_COUNT="$(jq -r '(.layers // []) | length' "$BLOB_FILE")"
        fi
    fi
fi

if [ -z "$LAYER_COUNT" ] || [ "$LAYER_COUNT" = "null" ] || ! [[ "$LAYER_COUNT" =~ ^[0-9]+$ ]] || [ "$LAYER_COUNT" -le 0 ]; then
    echo "[FAIL] Could not determine OCI layer count for ${IMAGE_REF} (got: '${LAYER_COUNT}')." >&2
    exit 1
fi
if [ "$LAYER_COUNT" -gt 96 ]; then
    echo "[FAIL] Image ${IMAGE_REF} has ${LAYER_COUNT} layers, exceeding the 96-layer bootc/ostree limit." >&2
    exit 1
fi
echo "[PASS] Verified ${IMAGE_REF} layer count: ${LAYER_COUNT} <= 96"

export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-auto}"
R2_ENDPOINT="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
R2_DEST="s3://${R2_BUCKET}/oci/${REPO_NAME}/"

echo "==> Syncing OCI directory to Cloudflare R2 (${R2_DEST})..."
aws s3 sync "${OCI_DIR}/" "${R2_DEST}" --endpoint-url "${R2_ENDPOINT}"
echo "[PASS] Synced ${IMAGE_REF} (${LAYER_COUNT} layers) to ${R2_DEST}"
