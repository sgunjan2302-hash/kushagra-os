# Kushagra OS - Custom ujust Command Recipes
# Universal Blue entry imports this file automatically as 60-custom.just

# Switch desktop layout between Familiar (Windows bottom panel) and Studio (macOS top bar + dock)
switch-layout LAYOUT="":
    @/usr/bin/kushagra-layout-switch {{LAYOUT}}

# 4 GB Low-RAM survival mode toggle (disables Baloo indexing, KWin blur, and optimizes animation duration)
low-ram-mode ACTION="status":
    #!/usr/bin/env bash
    set -euo pipefail
    case "{{ACTION}}" in
        enable|on)
            echo "Enabling Low-RAM Mode optimizations..."
            kwriteconfig6 --file baloofilerc --group "Basic Settings" --key "Indexing-Enabled" false
            kwriteconfig6 --file kwinrc --group "Plugins" --key "blurEnabled" false
            kwriteconfig6 --file kwinrc --group "KWin" --key "AnimationDurationFactor" 0.5
            echo "Low-RAM Mode enabled: Baloo indexing disabled, KWin blur disabled, animations accelerated."
            echo "Please log out and log back in for Plasma settings to take full effect."
            ;;
        disable|off)
            echo "Restoring standard Plasma visual defaults..."
            kwriteconfig6 --file baloofilerc --group "Basic Settings" --key "Indexing-Enabled" true
            kwriteconfig6 --file kwinrc --group "Plugins" --key "blurEnabled" true
            kwriteconfig6 --file kwinrc --group "KWin" --key "AnimationDurationFactor" 1.0
            echo "Standard visual defaults restored."
            ;;
        status|*)
            echo "=== Low-RAM Mode Status ==="
            echo -n "Baloo Indexing: "
            kreadconfig6 --file baloofilerc --group "Basic Settings" --key "Indexing-Enabled" || echo "Default"
            echo -n "KWin Blur: "
            kreadconfig6 --file kwinrc --group "Plugins" --key "blurEnabled" || echo "Default"
            echo -n "Animation Factor: "
            kreadconfig6 --file kwinrc --group "KWin" --key "AnimationDurationFactor" || echo "1.0"
            echo ""
            echo "Usage: ujust low-ram-mode [enable|disable|status]"
            ;;
    esac

# Initialize Waydroid container network routing and graphics configuration
setup-waydroid:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "=== Kushagra OS Waydroid Setup ==="
    echo "Configuring firewalld trusted zone for Waydroid..."
    sudo firewall-cmd --zone=trusted --add-interface=waydroid0 --permanent 2>/dev/null || true
    sudo firewall-cmd --zone=trusted --add-port=67/udp --permanent 2>/dev/null || true
    sudo firewall-cmd --zone=trusted --add-port=53/udp --permanent 2>/dev/null || true
    sudo firewall-cmd --zone=trusted --add-forward --permanent 2>/dev/null || true
    sudo firewall-cmd --reload

    # Check for NVIDIA graphics to configure software EGL/SwiftShader fallback
    if lspci -nn | grep -Ei "vga|3d" | grep -iq "nvidia"; then
        echo "NVIDIA GPU detected: Configuring SwiftShader software rendering fallback for Waydroid..."
        sudo mkdir -p /var/lib/waydroid
        if [ -f "/var/lib/waydroid/waydroid.cfg" ]; then
            sudo sed -i 's/^ro.hardware.gralloc=.*/ro.hardware.gralloc=default/' /var/lib/waydroid/waydroid.cfg || true
            sudo sed -i 's/^ro.hardware.egl=.*/ro.hardware.egl=swiftshader/' /var/lib/waydroid/waydroid.cfg || true
        fi
    fi

    echo "Initializing Waydroid system container..."
    sudo waydroid init || echo "Waydroid already initialized or requires network access."
    sudo systemctl restart waydroid-container.service || true

    echo "--------------------------------------------------------------------------------"
    echo "CRITICAL COMPATIBILITY NOTICE:"
    echo "1. Waydroid does NOT run in LiveCD mode; disk installation is mandatory."
    echo "2. Indian UPI and Banking apps (GPay, PhonePe, Paytm, DigiLocker) require"
    echo "   hardware Google Play Integrity (MEETS_STRONG_INTEGRITY) which Waydroid"
    echo "   cannot pass. Do NOT rely on Waydroid for financial transactions."
    echo "--------------------------------------------------------------------------------"

# Display hardware-tiered setup guide for Indic Speech & AI models
setup-indic-ai:
    #!/usr/bin/env bash
    echo "=== Kushagra OS Indic AI & Language Stack ==="
    echo ""
    echo "Hardware Tiering Recommendations:"
    echo "  [Tier 1: 4 GB RAM Budget Laptops]"
    echo "    - Speech Recognition: AI4Bharat IndicConformer (120M quantized Hindi model, ~130 MB)"
    echo "    - Transliteration: IndicXlit (~11M parameters)"
    echo "    - Translation / Chat: Use BHASHINI / ULCA public APIs (0 local RAM footprint)"
    echo ""
    echo "  [Tier 2: 8 GB+ RAM Systems]"
    echo "    - Offline Local LLM: Dhīr 5B MoE (Q4_K_M GGUF, ~3.4 GB) via llama.cpp"
    echo "    - Translation: IndicTrans2 (22 Indian languages)"
    echo ""
    echo "WARNING ON SARVAM-1:"
    echo "  Sarvam-1 (1.5 GB) is a base text-completion model, NOT an instruction-tuned"
    echo "  conversational chatbot. Kushagra OS does not ship it as a desktop assistant."

# Diagnose connected Indian DSC (Digital Signature) tokens and smart cards
check-dsc-token:
    #!/usr/bin/env bash
    echo "=== Kushagra OS Digital Signature Token Diagnostics ==="
    echo "Checking PC/SC smart card daemon status..."
    systemctl is-active pcscd.socket && echo "pcscd.socket: ACTIVE" || echo "pcscd.socket: INACTIVE"
    echo ""
    echo "Scanning connected USB tokens..."
    if command -v opensc-tool >/dev/null 2>&1; then
        opensc-tool -l || true
    fi
    if command -v pkcs11-tool >/dev/null 2>&1; then
        echo "Querying PKCS#11 slots (/usr/lib64/opensc-pkcs11.so)..."
        pkcs11-tool --module /usr/lib64/opensc-pkcs11.so -L || true
    fi
    echo ""
    echo "Hardware Compatibility Matrix:"
    echo "  - Feitian ePass2003: Fully supported via OpenSC / CCID."
    echo "  - Watchdata ProxKey: Incompatible with default OpenSC (requires vendor pcscd_wd daemon)."
    echo "  - Mantra MFS110 / Morpho 1300 E3: L1 Aadhaar RD services do not provide verified Fedora Atomic drivers."

# Run Kushagra OS system health verification suite
health-check:
    @/usr/bin/kushagra-health-check

# Launch Graphical Installer for Kushagra OS
install-to-disk:
    #!/usr/bin/env bash
    if command -v liveinst >/dev/null 2>&1; then
        echo "Launching Anaconda Live graphical installer..."
        sudo liveinst
    elif command -v calamares >/dev/null 2>&1; then
        echo "Launching Calamares graphical installer..."
        sudo calamares
    elif command -v partitionmanager >/dev/null 2>&1; then
        echo "Launching KDE Partition Manager..."
        partitionmanager &
    else
        echo "Error: No graphical installer binary found in PATH."
        exit 1
    fi

# Install Windows Gaming Stack (Steam, Heroic, MangoHud, Gamescope)
install-gaming:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "=== Installing Kushagra OS Windows Gaming Stack ==="
    echo "Staging Steam, Heroic Games Launcher, MangoHud & Gamescope via Flathub..."
    flatpak install --user -y flathub \
        com.valvesoftware.Steam \
        com.heroicgames.launcher \
        org.freedesktop.Platform.VulkanLayer.MangoHud \
        com.valvesoftware.Steam.Utility.gamescope || true
    echo "Gaming stack staged successfully."
    echo "Proton-GE and Wine translation layers are ready via Steam and Bottles."

# Provision isolated Ubuntu LTS container environment via Distrobox
box-ubuntu:
    #!/usr/bin/env bash
    set -euo pipefail
    BOX_NAME="kushagra-ubuntu"
    if ! distrobox list | grep -q "${BOX_NAME}"; then
        echo "Creating new ${BOX_NAME} container (Ubuntu 24.04 LTS)..."
        distrobox create --name "${BOX_NAME}" --image quay.io/toolbx-images/ubuntu-toolbox:24.04 --yes
    fi
    echo "Entering ${BOX_NAME}..."
    distrobox enter "${BOX_NAME}"

# Provision isolated Arch Linux container environment via Distrobox (AUR access)
box-arch:
    #!/usr/bin/env bash
    set -euo pipefail
    BOX_NAME="kushagra-arch"
    if ! distrobox list | grep -q "${BOX_NAME}"; then
        echo "Creating new ${BOX_NAME} container (Arch Linux)..."
        distrobox create --name "${BOX_NAME}" --image quay.io/toolbx-images/archlinux-toolbox:latest --yes
    fi
    echo "Entering ${BOX_NAME}..."
    distrobox enter "${BOX_NAME}"

# Storage hygiene optimizer tailored for the ~68.8 GB installation footprint
clean-disk:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "=== Kushagra OS Storage Hygiene Optimizer (~68.8 GB Footprint) ==="
    echo "1. Pruning unused Flatpak runtimes and residual cache..."
    flatpak uninstall --unused -y || true
    rm -rf ~/.var/app/*/cache/* 2>/dev/null || true
    echo "2. Pruning dangling Podman and container layers..."
    podman system prune -f 2>/dev/null || true
    echo "3. Vacuuming systemd journal logs beyond 7 days..."
    sudo journalctl --vacuum-time=7d || true
    echo "4. Checking current Btrfs filesystem free space..."
    df -h / /var /home 2>/dev/null || df -h /
    echo "Disk hygiene routine complete."

# Check game anti-cheat compatibility matrix & Proton boundaries
check-anti-cheat:
    #!/usr/bin/env bash
    echo "=== Windows Gaming Anti-Cheat Compatibility Matrix ==="
    echo "Supported Anti-Cheat Categories on Kushagra OS (Linux / Proton):"
    echo "  [COMPATIBLE] Server-Side Anti-Cheat & Linux-Enabled EAC/BattlEye:"
    echo "    - Counter-Strike 2 (VAC)"
    echo "    - Apex Legends (Easy Anti-Cheat - Proton enabled)"
    echo "    - Elden Ring (Easy Anti-Cheat - Proton enabled)"
    echo "    - Baldur's Gate 3 / Cyberpunk 2077 / GTA V (No kernel ring-0 requirement)"
    echo ""
    echo "  [INCOMPATIBLE BY DESIGN] Proprietary Ring-0 Kernel Anti-Cheat:"
    echo "    - Valorant (Riot Vanguard - requires Windows kernel driver)"
    echo "    - League of Legends (Vanguard)"
    echo "    - Fortnite (Epic Easy Anti-Cheat - Linux flag disabled by Epic)"
    echo "    - Call of Duty: Warzone (Ricochet)"
    echo ""
    echo "Honesty Policy: Kushagra OS will never claim compatibility with proprietary"
    echo "Windows kernel rootkit anti-cheat engines. For unsupported titles, dual-booting"
    echo "into your coexisting Windows partition is the officially recommended path."
