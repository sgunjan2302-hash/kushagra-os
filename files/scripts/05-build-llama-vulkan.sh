#!/usr/bin/env bash
set -euo pipefail

echo "==> [Hook 05] Building lightweight Vulkan + CPU llama-server (zero ROCm bloat)..."

LLAMA_REPO="https://github.com/ggml-org/llama.cpp.git"
LLAMA_TAG="b12823"
PRE_RPMS="/tmp/pre_llama_rpms.txt"
SRC_DIR="/tmp/llama-cpp-src"

cleanup_tmp() {
    rm -rf -- "${PRE_RPMS}" "${SRC_DIR}"
}
trap cleanup_tmp EXIT

# 1. Snapshot pre-existing RPM packages before installing ephemeral build tools
if command -v rpm >/dev/null 2>&1; then
    rpm -qa --qf '%{NAME}\n' | sort -u > "${PRE_RPMS}"
else
    : > "${PRE_RPMS}"
fi

# 2. Install minimal Vulkan + C++ build dependencies (strictly NO COPR, NO ROCm/CUDA)
BUILD_DEPS=(
    cmake
    ninja-build
    gcc-c++
    git
    binutils
    vulkan-headers
    vulkan-loader-devel
    spirv-headers-devel
    glslc
)

echo "Installing ephemeral Vulkan llama.cpp build dependencies via dnf5..."
dnf5 install -y --setopt=install_weak_deps=False "${BUILD_DEPS[@]}"

# 3. Shallow-clone pinned ggml-org/llama.cpp release tag
rm -rf -- "${SRC_DIR}"
echo "Cloning ${LLAMA_REPO} (${LLAMA_TAG})..."
GIT_TERMINAL_PROMPT=0 git clone --depth 1 --branch "${LLAMA_TAG}" "${LLAMA_REPO}" "${SRC_DIR}"

# 4. Configure ONLY llama-server with Vulkan + CPU backends (zero native-CPU assumptions, zero ROCm/CUDA/WebUI fetch)
echo "Configuring llama.cpp (${LLAMA_TAG}) with CMake..."
cmake -S "${SRC_DIR}" -B "${SRC_DIR}/build" \
    -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr \
    -DCMAKE_INSTALL_LIBDIR=lib64 \
    -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON \
    -DCMAKE_INSTALL_RPATH=/usr/lib64 \
    -DGGML_VULKAN=ON \
    -DGGML_NATIVE=OFF \
    -DGGML_HIP=OFF \
    -DGGML_CUDA=OFF \
    -DLLAMA_CURL=OFF \
    -DLLAMA_OPENSSL=OFF \
    -DLLAMA_BUILD_TESTS=OFF \
    -DLLAMA_BUILD_EXAMPLES=OFF \
    -DLLAMA_BUILD_SERVER=ON \
    -DLLAMA_BUILD_UI=OFF \
    -DLLAMA_USE_PREBUILT_UI=OFF \
    -DBUILD_SHARED_LIBS=ON

echo "Building llama-server target with Ninja..."
cmake --build "${SRC_DIR}/build" --target llama-server -j"$(nproc)"

# 5. Install ONLY stripped /usr/bin/llama-server and required runtime shared libraries
BIN_OUT="${SRC_DIR}/build/bin"
if [ ! -x "${BIN_OUT}/llama-server" ]; then
    echo "ERROR: ${BIN_OUT}/llama-server was not produced!" >&2
    exit 1
fi

install -d -m 0755 /usr/bin /usr/lib64
install -m 0755 "${BIN_OUT}/llama-server" /usr/bin/llama-server
strip --strip-unneeded /usr/bin/llama-server

INSTALLED_LIBS=()
while IFS= read -r -d '' libpath; do
    base="$(basename "${libpath}")"
    cp -a "${libpath}" "/usr/lib64/${base}"
    if [ ! -L "/usr/lib64/${base}" ] && [ -f "/usr/lib64/${base}" ]; then
        strip --strip-unneeded "/usr/lib64/${base}" || true
        chmod 0755 "/usr/lib64/${base}"
    fi
    INSTALLED_LIBS+=("/usr/lib64/${base}")
done < <(find "${BIN_OUT}" -maxdepth 1 -name 'lib*.so*' -print0 | sort -z)

if [ "${#INSTALLED_LIBS[@]}" -eq 0 ]; then
    echo "ERROR: No shared libraries (libllama*/libggml*) found in ${BIN_OUT}!" >&2
    exit 1
fi

ldconfig

echo "Installed stripped llama-server and runtime libraries:"
du -ch /usr/bin/llama-server "${INSTALLED_LIBS[@]}" || true

# 6. Remove newly added build/-devel RPMs while preserving jq, vulkan-loader, libgomp, and OS runtime libraries
if command -v rpm >/dev/null 2>&1 && command -v dnf5 >/dev/null 2>&1 && [ -s "${PRE_RPMS}" ]; then
    RUNTIME_KEEP_RE='^(jq|bash|glibc.*|systemd.*|python3|vulkan-loader|libgomp|libstdc\+\+|libgcc|zlib-ng-compat)$'
    mapfile -t NEW_BUILD_RPMS < <(
        comm -13 "${PRE_RPMS}" <(rpm -qa --qf '%{NAME}\n' | sort -u) | \
        grep -E '(-devel$|-headers$|-static$|-rpm-macros$|^cmake.*|^ninja-build$|^gcc.*|^cpp$|^binutils.*|^git$|^git-core$|^perl-Git$|^glslc$|^libshaderc$|^spirv-.*|^rhash$|^pkgconf.*|^annobin.*|^dwz$|^redhat-rpm-config$|^make$)' | \
        grep -Ev "${RUNTIME_KEEP_RE}" || true
    )
    if [ "${#NEW_BUILD_RPMS[@]}" -gt 0 ]; then
        echo "Removing ${#NEW_BUILD_RPMS[@]} newly added build/-devel RPMs..."
        dnf5 remove -y "${NEW_BUILD_RPMS[@]}" || true
    fi

    mapfile -t LEFTOVER_BUILD_RPMS < <(
        comm -13 "${PRE_RPMS}" <(rpm -qa --qf '%{NAME}\n' | sort -u) | \
        grep -Ev "${RUNTIME_KEEP_RE}" || true
    )
    if [ "${#LEFTOVER_BUILD_RPMS[@]}" -gt 0 ]; then
        echo "Removing ${#LEFTOVER_BUILD_RPMS[@]} leftover newly added build RPMs: ${LEFTOVER_BUILD_RPMS[*]}"
        dnf5 remove -y "${LEFTOVER_BUILD_RPMS[@]}" || true
    fi
fi

rm -rf -- "${PRE_RPMS}" "${SRC_DIR}"
dnf5 clean all || true
ldconfig

# 7. Verify post-cleanup dynamic linkage & Vulkan device listing
echo "Verifying post-cleanup shared library linkage for /usr/bin/llama-server..."
if ldd /usr/bin/llama-server | grep -q 'not found'; then
    echo "ERROR: Missing runtime shared library in /usr/bin/llama-server!" >&2
    ldd /usr/bin/llama-server >&2
    exit 1
fi
ldd /usr/bin/llama-server

echo "Verifying /usr/bin/llama-server --version and --list-devices..."
/usr/bin/llama-server --version
if dev_out="$(/usr/bin/llama-server --list-devices 2>&1)"; then
    printf '%s\n' "${dev_out}"
else
    echo "Notice: /usr/bin/llama-server --list-devices reported no active GPU in headless container (CPU mode intact):"
    printf '%s\n' "${dev_out}"
fi

echo "==> [Hook 05] Lightweight Vulkan llama-server installation complete."
