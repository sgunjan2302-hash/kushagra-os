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
