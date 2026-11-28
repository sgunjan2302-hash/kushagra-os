#!/usr/bin/env bash
set -euo pipefail

echo "==> [Hook 04] Building Safe Liquid Glass UI (KWin Glass Effect & Palette)..."

PRE_RPMS="/tmp/pre_glass_rpms.txt"
PRE_PLUGINS="/tmp/pre_glass_plugins.txt"
POST_PLUGINS="/tmp/post_glass_plugins.txt"
SRC_DIR="/tmp/kwin-glass-src"
PLUGIN_DIR="/usr/lib64/qt6/plugins/kwin/effects/plugins"
BACKEND_FILE="/etc/kushagra-glass-backend"

cleanup_tmp() {
    rm -rf -- "${PRE_RPMS}" "${PRE_PLUGINS}" "${POST_PLUGINS}" "${SRC_DIR}"
}
trap cleanup_tmp EXIT

# 1. Capture pre-installed RPM package names and existing KWin effect plugins
if command -v rpm >/dev/null 2>&1; then
    rpm -qa --qf '%{NAME}\n' | sort -u > "${PRE_RPMS}"
else
    : > "${PRE_RPMS}"
fi

if [ -d "${PLUGIN_DIR}" ]; then
    find "${PLUGIN_DIR}" -maxdepth 1 -name '*.so' -printf '%f\n' | sort -u > "${PRE_PLUGINS}"
else
    : > "${PRE_PLUGINS}"
fi

# 2. Install Fedora 44 -devel/build dependencies (strictly NO COPR repos)
BUILD_DEPS=(
    kwin-devel
    extra-cmake-modules
    cmake
    ninja-build
    gcc-c++
    git
    gettext
    kf6-kconfig-devel
    kf6-kwindowsystem-devel
    kf6-kcmutils-devel
    kf6-kcoreaddons-devel
    kf6-kguiaddons-devel
    kf6-ki18n-devel
    kf6-kwidgetsaddons-devel
    kdecoration-devel
    libplasma-devel
    qt6-qtbase-devel
    qt6-qtbase-private-devel
    qt6-qtdeclarative-devel
    qt6-qttools-devel
    qt6-qtwayland-devel
    wayland-devel
    plasma-wayland-protocols-devel
    libepoxy-devel
    libdrm-devel
    mesa-libGL-devel
    mesa-libEGL-devel
    mesa-libgbm-devel
    vulkan-loader-devel
)

DEPS_INSTALLED=0
if command -v dnf5 >/dev/null 2>&1; then
    echo "Installing KWin glass build dependencies via dnf5..."
    if dnf5 install -y --setopt=install_weak_deps=False "${BUILD_DEPS[@]}"; then
        DEPS_INSTALLED=1
    else
        echo "Notice: dnf5 build dependency install failed; skipping upstream KWin glass compilation."
    fi
else
    echo "Notice: dnf5 not available; skipping upstream KWin glass compilation."
fi

# 3. Guarded build attempt against Plasma 6.8.3 headers with clean fallback
INSTALLED_BACKEND=""
INSTALLED_PLUGIN=""
INSTALLED_SO=""

try_build_glass() {
    local repo_url="$1"
    local backend_label="$2"
    local config_dir="/usr/lib64/qt6/plugins/kwin/effects/configs"
    local pre_configs="/tmp/pre_glass_configs.txt"
    local post_configs="/tmp/post_glass_configs.txt"

    if [ -d "${config_dir}" ]; then
        find "${config_dir}" -maxdepth 1 -name '*.so' -printf '%f\n' | sort -u > "${pre_configs}"
    else
        : > "${pre_configs}"
    fi

    rm -rf -- "${SRC_DIR}"
    echo "Attempting shallow clone (${repo_url})..."
    if ! GIT_TERMINAL_PROMPT=0 git clone --depth 1 "${repo_url}" "${SRC_DIR}"; then
        echo "Notice: git clone failed for ${repo_url}."
        rm -rf -- "${SRC_DIR}" "${pre_configs}" "${post_configs}"
        return 1
    fi

    echo "Configuring ${backend_label} with CMake (-G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr -DGLASS_WAYLAND=ON -DGLASS_X11=OFF)..."
    if ! cmake -S "${SRC_DIR}" -B "${SRC_DIR}/build" \
        -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/usr \
        -DGLASS_WAYLAND=ON \
        -DGLASS_X11=OFF; then
        echo "Notice: CMake configuration failed for ${backend_label}."
        rm -rf -- "${SRC_DIR}" "${pre_configs}" "${post_configs}"
        return 1
    fi

    echo "Compiling ${backend_label} with ninja..."
    if ! ninja -C "${SRC_DIR}/build"; then
        echo "Notice: Ninja compilation failed for ${backend_label} against Plasma 6.8.3 headers."
        rm -rf -- "${SRC_DIR}" "${pre_configs}" "${post_configs}"
        return 1
    fi

    echo "Installing ${backend_label} into /usr..."
    if ! DESTDIR="" ninja -C "${SRC_DIR}/build" install; then
        echo "Notice: ninja install failed for ${backend_label}."
        rm -rf -- "${SRC_DIR}" "${pre_configs}" "${post_configs}"
        return 1
    fi

    if [ -d "${PLUGIN_DIR}" ]; then
        find "${PLUGIN_DIR}" -maxdepth 1 -name '*.so' -printf '%f\n' | sort -u > "${POST_PLUGINS}"
    else
        : > "${POST_PLUGINS}"
    fi
    if [ -d "${config_dir}" ]; then
        find "${config_dir}" -maxdepth 1 -name '*.so' -printf '%f\n' | sort -u > "${post_configs}"
    else
        : > "${post_configs}"
    fi

    local new_so new_cfg
    new_so="$(comm -13 "${PRE_PLUGINS}" "${POST_PLUGINS}" | head -n1 || true)"
    new_cfg="$(comm -13 "${pre_configs}" "${post_configs}" | head -n1 || true)"
    rm -f -- "${pre_configs}" "${post_configs}"

    if [ -n "${new_so}" ] && [ -f "${PLUGIN_DIR}/${new_so}" ]; then
        INSTALLED_BACKEND="${backend_label}"
        INSTALLED_PLUGIN="${new_so%.so}"
        INSTALLED_SO="${PLUGIN_DIR}/${new_so}"
        if command -v strip >/dev/null 2>&1; then
            strip --strip-unneeded "${INSTALLED_SO}" || true
            if [ -n "${new_cfg}" ] && [ -f "${config_dir}/${new_cfg}" ]; then
                strip --strip-unneeded "${config_dir}/${new_cfg}" || true
            fi
        fi
        rm -rf -- "${SRC_DIR}"
        return 0
    fi

    echo "Notice: ${backend_label} installed, but no new plugin .so appeared in ${PLUGIN_DIR}; rolling back manifest."
    if [ -f "${SRC_DIR}/build/install_manifest.txt" ]; then
        while IFS= read -r installed_file; do
            if [ -n "${installed_file}" ] && [ -f "${installed_file}" ]; then
                rm -f -- "${installed_file}" || true
            fi
        done < "${SRC_DIR}/build/install_manifest.txt"
    fi
    rm -rf -- "${SRC_DIR}"
    return 1
}

if [ "${DEPS_INSTALLED}" -eq 1 ] && command -v git >/dev/null 2>&1 && command -v cmake >/dev/null 2>&1 && command -v ninja >/dev/null 2>&1; then
    if try_build_glass "https://github.com/4v3ngR/kwin-effects-glass.git" "kwin-effects-glass"; then
        echo "Compiled and installed kwin-effects-glass plugin (${INSTALLED_SO})."
    fi
fi

mkdir -p "$(dirname "${BACKEND_FILE}")"
if [ -n "${INSTALLED_BACKEND}" ] && [ -n "${INSTALLED_PLUGIN}" ]; then
    cat <<EOF > "${BACKEND_FILE}"
backend=${INSTALLED_BACKEND}
plugin=${INSTALLED_PLUGIN}
plugin_path=${INSTALLED_SO}
EOF
    echo "Recorded active KWin glass backend in ${BACKEND_FILE}: backend=${INSTALLED_BACKEND}, plugin=${INSTALLED_PLUGIN}"
else
    echo "Notice: Upstream KWin glass effect failed to compile against Plasma 6.8.3 headers; falling back cleanly to stock KWin blur + Kushagra Glass rounded palette."
    rm -rf -- "${SRC_DIR}"
    cat <<'EOF' > "${BACKEND_FILE}"
backend=stock-blur-fallback
EOF
fi
chmod 0644 "${BACKEND_FILE}"

# 4. Remove ALL newly added build/-devel/toolchain RPMs while protecting core OS runtime packages
if command -v rpm >/dev/null 2>&1 && command -v dnf5 >/dev/null 2>&1 && [ -s "${PRE_RPMS}" ]; then
    RUNTIME_KEEP_RE='^(jq|bash|glibc|glibc-common|glibc-all-langpacks|systemd|systemd-libs|systemd-udev|systemd-pam|systemd-resolved|systemd-oomd-defaults|kwin|kwin-libs|kwin-common|plasma-desktop|qt6-qtbase|qt6-qtbase-common|qt6-qtbase-gui|qt6-qtdeclarative|qt6-qtwayland|python3|vulkan-loader|libgomp|kdecoration|libplasma|libepoxy|libdrm|mesa-libGL|mesa-libEGL|mesa-libgbm)$'
    mapfile -t NEW_BUILD_RPMS < <(
        comm -13 "${PRE_RPMS}" <(rpm -qa --qf '%{NAME}\n' | sort -u) | \
        grep -E '(-devel$|-headers$|-static$|-rpm-macros$|^cmake$|^cmake-data$|^cmake-filesystem$|^ninja-build$|^extra-cmake-modules$|^gcc$|^gcc-c\+\+$|^cpp$|^binutils$|^git$|^git-core$|^perl-Git$|^gettext$|^doxygen$|^clang-libs$|^clang-resource-filesystem$|^graphviz.*|^gts$|^lasi$|^netpbm$|^poppler-glib$|^kde-qdoc-common$|^qt6-designer$|^qt6-doctools$|^qt6-linguist$|^qt6-qtbase-(ibase|odbc|postgresql)$|^qt6-qttools-.*|^libfbclient2$|^libpq$|^unixODBC$|^pkgconf.*|^annobin.*|^gcc-plugin-annobin$|^dwz$|^redhat-rpm-config$|^rhash$|^spdlog$|^make$)' | \
        grep -Ev "${RUNTIME_KEEP_RE}" || true
    )
    if [ "${#NEW_BUILD_RPMS[@]}" -gt 0 ]; then
        echo "Removing ${#NEW_BUILD_RPMS[@]} newly added build/-devel RPMs..."
        dnf5 remove -y "${NEW_BUILD_RPMS[@]}" || true
    fi

    mapfile -t LEFTOVER_DEVEL < <(
        comm -13 "${PRE_RPMS}" <(rpm -qa --qf '%{NAME}\n' | sort -u) | \
        grep -Ev "${RUNTIME_KEEP_RE}" || true
    )
    if [ "${#LEFTOVER_DEVEL[@]}" -gt 0 ]; then
        echo "Removing ${#LEFTOVER_DEVEL[@]} leftover newly added build packages: ${LEFTOVER_DEVEL[*]}"
        dnf5 remove -y "${LEFTOVER_DEVEL[@]}" || true
    fi
fi

if [ -n "${INSTALLED_SO}" ] && [ -f "${INSTALLED_SO}" ] && command -v ldd >/dev/null 2>&1; then
    echo "Verifying shared library linkage for ${INSTALLED_SO}..."
    if ldd "${INSTALLED_SO}" | grep -q 'not found'; then
        echo "ERROR: Missing shared library dependency in ${INSTALLED_SO} after cleanup!" >&2
        ldd "${INSTALLED_SO}" >&2
        exit 1
    fi
fi

rm -rf -- "${PRE_RPMS}" "${PRE_PLUGINS}" "${POST_PLUGINS}" "${SRC_DIR}"
if command -v dnf5 >/dev/null 2>&1; then
    dnf5 clean all || true
fi

# 5. Enforce permissions & globally enable Kushagra Glass user guard
for bin in /usr/bin/kushagra-glass-toggle /usr/bin/kushagra-glass-guard; do
    if [ -f "${bin}" ]; then
        chmod 0755 "${bin}"
    fi
done

for cfg in \
    /etc/xdg/kwinrulesrc \
    /etc/xdg/kdeglobals \
    /etc/kushagra-glass-backend \
    /usr/share/color-schemes/KushagraGlassDark.colors \
    /usr/share/color-schemes/KushagraGlassLight.colors \
    /usr/lib/systemd/user/kushagra-glass-guard.service; do
    if [ -f "${cfg}" ]; then
        chmod 0644 "${cfg}"
    fi
done

if command -v systemctl >/dev/null 2>&1 && [ -f /usr/lib/systemd/user/kushagra-glass-guard.service ]; then
    systemctl --global enable kushagra-glass-guard.service || true
fi

echo "==> [Hook 04] Safe Liquid Glass UI configuration complete."
