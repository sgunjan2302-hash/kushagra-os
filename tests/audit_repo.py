import ast
import glob
import os
import re
import sys
import xml.etree.ElementTree as ET
import yaml

results = []


def record(name, status, detail):
    results.append({'name': name, 'status': status, 'detail': detail})
    print(f"[{status}] {name}: {detail}")


# 1. Secret Safety
git_ignored = open('.gitignore', 'r', encoding='utf-8').read()
has_keys = all(k in git_ignored for k in ['*.key', '*.private', '*.secret', 'cosign.key'])

tracked_sec_files = []
try:
    import subprocess
    tracked = subprocess.check_output(['git', 'ls-files'], text=True).splitlines()
    tracked_sec_files = [f for f in tracked if f.endswith('.key') or f.endswith('.private') or f.endswith('.secret')]
except Exception:
    pass

if has_keys and len(tracked_sec_files) == 0:
    record('Secret Safety', 'PASS', '.gitignore blocks private keys; 0 private keys tracked by Git')
else:
    record('Secret Safety', 'FAIL', f'Private key files tracked by Git: {tracked_sec_files}')

# 2. YAML Safe Parsing
yaml_files = glob.glob('recipes/*.yml') + glob.glob('.github/workflows/*.yml') + ['files/system/usr/lib/bootc-image-builder/iso.yaml']
yaml_failures = []
for yf in yaml_files:
    try:
        with open(yf, 'r', encoding='utf-8') as fp:
            yaml.safe_load(fp)
    except Exception as e:
        yaml_failures.append(f'{yf}: {e}')

if not yaml_failures:
    record('YAML Safe Parsing', 'PASS', f'All {len(yaml_files)} YAML files parsed cleanly')
else:
    record('YAML Safe Parsing', 'FAIL', str(yaml_failures))

# 3. Anti-Pattern Scan (checking active configuration, ignoring comment lines)
banned_patterns = {
    'rpm-ostree': 'recipes/recipe.yml',
    'optfix:': 'recipes/recipe.yml',
    '/usr/etc/': 'recipes/recipe.yml',
    'rechunk:': '.github/workflows/build.yml',
    'GTK_IM_MODULE': 'files/system/etc/environment',
    'QT_IM_MODULE': 'files/system/etc/environment',
    'DNSOverTLS=yes': 'files/system/etc/systemd/resolved.conf.d/10-dot-opportunistic.conf',
    '9.9.9.10': 'files/system/etc/systemd/resolved.conf.d/10-dot-opportunistic.conf',
    '149.112.112.10': 'files/system/etc/systemd/resolved.conf.d/10-dot-opportunistic.conf',
    'clamav-data': 'recipes/packages.yml',
    'clamd': 'recipes/packages.yml',
    'usbguard.service': 'recipes/recipe.yml',
}
anti_failures = []
for pattern, path in banned_patterns.items():
    if os.path.exists(path):
        lines = open(path, 'r', encoding='utf-8').readlines()
        for idx, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('#') or stripped.startswith('//'):
                continue
            if pattern in line:
                anti_failures.append(f'{pattern} found in active config {path}:{idx} -> {stripped}')

with open('recipes/recipe.yml', 'r', encoding='utf-8') as fp:
    recipe_text = fp.read()
    init_count = recipe_text.count('type: initramfs')
    if init_count != 1:
        anti_failures.append(f'type: initramfs count is {init_count} (expected 1)')

if not anti_failures:
    record('Anti-Pattern Audit', 'PASS', 'Zero banned anti-patterns detected; initramfs count is exactly 1')
else:
    record('Anti-Pattern Audit', 'FAIL', '; '.join(anti_failures))

# 4. XML Check
try:
    tree = ET.parse('files/system/etc/firewalld/zones/kushagra-workstation.xml')
    services = [s.attrib.get('name') for s in tree.getroot().findall('service')]
    if 'ssh' not in services and set(services) == {'dhcpv6-client', 'mdns', 'ipp-client', 'kdeconnect'}:
        record('Firewalld XML Validation', 'PASS', f'kushagra-workstation.xml clean (services: {services})')
    else:
        record('Firewalld XML Validation', 'FAIL', f'Unexpected services: {services}')
except Exception as e:
    record('Firewalld XML Validation', 'FAIL', str(e))

# 5. JavaScript Check
js_files = glob.glob('files/system/usr/share/kushagra-os/layouts/*.js')
js_ok = True
for j in js_files:
    c = open(j, 'r', encoding='utf-8').read()
    if 'lengthMode = "fill"' not in c and 'lengthMode = "fit"' not in c:
        record(f'JS Layout API ({j})', 'FAIL', 'Missing string lengthMode')
        js_ok = False
if js_ok:
    record('JS Layout API Validation', 'PASS', 'Both windows-classic.js and modern-floating.js use string lengthMode')

# 6. Line Endings Check (scripts, OOBE/Installer/WinRun Python/QML, systemd unit, MIME/profile)
lf_targets = (
    glob.glob('files/scripts/*.sh')
    + glob.glob('files/system/usr/bin/kushagra-*')
    + glob.glob('files/system/usr/bin/k-ai-*')
    + glob.glob('files/system/usr/libexec/kushagra-*')
    + glob.glob('files/system/usr/libexec/k-ai-*')
    + glob.glob('files/system/usr/share/kushagra-os/oobe/*.py')
    + glob.glob('files/system/usr/share/kushagra-os/oobe/*.qml')
    + glob.glob('files/system/usr/share/kushagra-os/installer/*.py')
    + glob.glob('files/system/usr/share/kushagra-os/installer/*.qml')
    + glob.glob('files/system/usr/share/kushagra-os/winrun/*.py')
    + glob.glob('files/system/usr/share/kushagra-os/apkrun/*.py')
    + glob.glob('files/system/usr/share/kushagra-os/kai/*.py')
    + glob.glob('files/system/usr/share/kushagra-os/kai/*.qml')
    + [
        'files/system/usr/share/kushagra-os/kai/actions.json',
        'files/system/usr/share/kushagra-os/livesys/livesys-session-extra',
        'files/system/usr/lib/systemd/system-generators/kushagra-live-plymouth-generator',
        'files/system/usr/lib/systemd/system/kushagra-oobe.service',
        'files/system/usr/lib/systemd/system/kushagra-dualboot-detect.service',
        'files/system/usr/lib/systemd/user/kushagra-installer.service',
        'files/system/usr/lib/systemd/user/kushagra-oobe-ui.service',
        'files/system/usr/lib/systemd/user/kushagra-glass-guard.service',
        'files/system/usr/lib/systemd/user/k-ai-engine.socket',
        'files/system/usr/lib/systemd/user/k-ai-engine.service',
        'files/system/usr/lib/tmpfiles.d/kushagra-oobe.conf',
        'files/system/usr/lib/tmpfiles.d/kushagra-kavach.conf',
        'files/system/usr/lib/bootc/kargs.d/10-kushagra-boot.toml',
        'files/system/etc/plymouth/plymouthd.conf',
        'files/system/etc/dracut.conf.d/plymouth-kms.conf',
        'files/system/etc/modules-load.d/90-kushagra-ntsync.conf',
        'files/system/etc/udev/rules.d/90-kushagra-ntsync.rules',
        'files/system/usr/share/plymouth/themes/kushagra/kushagra.plymouth',
        'files/system/etc/xdg/kwinrc',
        'files/system/etc/xdg/kwinrulesrc',
        'files/system/etc/xdg/kdeglobals',
        'files/system/usr/share/color-schemes/KushagraGlassDark.colors',
        'files/system/usr/share/color-schemes/KushagraGlassLight.colors',
        'files/system/etc/xdg/kglobalshortcutsrc',
        'files/system/etc/xdg/kded6rc',
        'files/system/etc/xdg/plasma-welcomerc',
        'files/system/etc/xdg/autostart/org.kde.plasma-welcome.desktop',
        'files/system/etc/skel/.config/kwinrc',
        'files/system/etc/skel/.config/kglobalshortcutsrc',
        'files/system/etc/skel/.config/fcitx5/profile',
        'files/system/etc/skel/.config/plasma-welcomerc',
        'files/system/etc/skel/.config/ksplashrc',
        'files/system/etc/systemd/resolved.conf.d/10-dot-opportunistic.conf',
        'files/system/etc/systemd/system/usbguard.service.d/10-kushagra-safe.conf',
        'files/system/etc/polkit-1/rules.d/50-kushagra-kavach.rules',
        'files/system/etc/polkit-1/rules.d/50-kushagra-kai.rules',
        'files/system/usr/share/kio/servicemenus/kushagra-kavach-scan.desktop',
        'files/system/usr/share/kio/servicemenus/kushagra-resolve-convert.desktop',
        'files/system/usr/share/applications/kushagra-apkrun.desktop',
        'files/system/usr/share/applications/k-ai-drawer.desktop',
        'files/system/usr/share/applications/k-ai-followalong.desktop',
        'files/system/usr/share/applications/k-ai-ocr.desktop',
        'files/system/usr/share/applications/kushagra-reboot-windows.desktop',
        'files/system/usr/share/krunner/dbusplugins/k-ai-krunner.desktop',
        'files/system/usr/share/dbus-1/services/org.kushagraos.KAI.Runner.service',
        'files/system/etc/anaconda/profile.d/kushagra-os.conf',
        'files/system/etc/xdg/mimeapps.list',
        'files/system/etc/issue.net',
        'files/system/etc/systemd/system/system-flatpak-setup.service.d/10-skip-livecd.conf',
        'files/system/etc/systemd/system/system-flatpak-setup.timer.d/10-skip-livecd.conf',
        'files/system/etc/systemd/system/bootloader-update.service.d/10-kushagra-live-guard.conf',
        'files/system/usr/share/ublue-os/just/60-custom.just',
    ]
)
crlf_files = []
for s in lf_targets:
    raw = open(s, 'rb').read()
    if b'\r' in raw:
        crlf_files.append(s)
if not crlf_files:
    record('LF Line Endings', 'PASS', f'All {len(lf_targets)} scripts/OOBE files have clean Unix LF')
else:
    record('LF Line Endings', 'FAIL', f'CRLF detected in: {crlf_files}')

# 7. Check 60-custom.just existence and location
just_file = 'files/system/usr/share/ublue-os/just/60-custom.just'
if os.path.exists(just_file):
    record('60-custom.just Location', 'PASS', f'Found at {just_file}')
else:
    record('60-custom.just Location', 'FAIL', f'Missing {just_file}')

# 8. Validate Titanoboa iso.yaml Contract (Zero-Text Silent Boot + Safe Graphics Recovery)
try:
    with open('files/system/usr/lib/bootc-image-builder/iso.yaml', 'r', encoding='utf-8') as fp:
        iso_cfg = yaml.safe_load(fp)
    grub2_cfg = iso_cfg.get('grub2', {})
    entries = grub2_cfg.get('entries', [])
    valid_entries = all('name' in e and 'linux' in e and 'initrd' in e for e in entries)
    has_enforcing = all('enforcing=0' in e.get('linux', '') for e in entries)
    entry0_linux = entries[0].get('linux', '') if len(entries) >= 1 else ''
    entry1_linux = entries[1].get('linux', '') if len(entries) >= 2 else ''
    silent_entry0 = (
        grub2_cfg.get('timeout') in (0, 1)
        and 'console=ttyS0' not in entry0_linux
        and all(
            tok in entry0_linux
            for tok in [
                'quiet',
                'splash',
                'rhgb',
                'loglevel=3',
                'systemd.show_status=false',
                'rd.systemd.show_status=auto',
                'rd.udev.log_level=3',
                'udev.log_priority=3',
                'vt.global_cursor_default=0',
            ]
        )
    )
    verbose_entry1 = (
        'nomodeset' in entry1_linux
        and 'console=tty0 console=ttyS0' in entry1_linux
        and 'systemd.show_status=true' in entry1_linux
    )
    if iso_cfg.get('label') and len(entries) >= 2 and valid_entries and has_enforcing and silent_entry0 and verbose_entry1:
        record(
            'Titanoboa iso.yaml Contract',
            'PASS',
            f'Label "{iso_cfg.get("label")}" silent Entry 0 (no ttyS0) + Safe Graphics/Verbose Entry 1 verified',
        )
    else:
        record(
            'Titanoboa iso.yaml Contract',
            'FAIL',
            f'valid_entries={valid_entries}, has_enforcing={has_enforcing}, '
            f'silent_entry0={silent_entry0}, verbose_entry1={verbose_entry1}',
        )
except Exception as e:
    record('Titanoboa iso.yaml Contract', 'FAIL', str(e))

# 9. LiveCD Initramfs Dracut Modules Contract
try:
    with open('recipes/packages.yml', 'r', encoding='utf-8') as f:
        pkgs_cfg = yaml.safe_load(f)
    install_pkgs = pkgs_cfg.get('install', {}).get('packages', [])
    has_dracut_live = 'dracut-live' in install_pkgs
    has_plymouth_pkgs = 'plymouth' in install_pkgs and 'plymouth-theme-spinner' in install_pkgs

    has_live_conf = os.path.exists('files/system/etc/dracut.conf.d/livecd.conf')
    has_kms_conf = os.path.exists('files/system/etc/dracut.conf.d/plymouth-kms.conf')
    conf_valid = False
    kms_valid = False
    if has_live_conf:
        with open('files/system/etc/dracut.conf.d/livecd.conf', 'r', encoding='utf-8') as f:
            conf_text = f.read()
            conf_valid = 'dmsquash-live' in conf_text
    if has_kms_conf:
        with open('files/system/etc/dracut.conf.d/plymouth-kms.conf', 'r', encoding='utf-8') as f:
            kms_text = f.read()
            kms_valid = (
                all(k in kms_text for k in ['plymouth', 'drm', 'amdgpu', 'i915', 'xe'])
                and 'force_drivers' not in kms_text
                and 'simpledrm' not in kms_text
                and 'nvidia' not in kms_text
            )

    if has_dracut_live and has_plymouth_pkgs and conf_valid and kms_valid:
        record('LiveCD Dracut Modules', 'PASS', 'dracut-live, plymouth, spinner, dmsquash-live, and safe amdgpu/i915/xe KMS verified')
    else:
        record('LiveCD Dracut Modules', 'FAIL', f'has_dracut_live={has_dracut_live}, has_plymouth_pkgs={has_plymouth_pkgs}, conf_valid={conf_valid}, kms_valid={kms_valid}')
except Exception as e:
    record('LiveCD Dracut Modules', 'FAIL', str(e))

# 10. UEFI LiveCD Bootloader Hardening & Silent GRUB Contract
try:
    with open('.github/workflows/iso.yml', 'r', encoding='utf-8') as f:
        iso_workflow = f.read()
    has_grub_boot_stage = '/out/EFI/BOOT/grubx64.efi' in iso_workflow
    has_fb_purge = 'fbx64.efi' in iso_workflow and 'rm -vf' in iso_workflow
    has_tpm_unload = 'rmmod tpm' in iso_workflow
    active_iso_lines = [ln.strip() for ln in iso_workflow.splitlines() if ln.strip() and not ln.strip().startswith('#')]
    has_hidden_grub = (
        'timeout_style=hidden' in iso_workflow
        and not any(re.search(r'\bif\s+keystatus\b|"if keystatus\b', ln) for ln in active_iso_lines)
    )

    if has_grub_boot_stage and has_fb_purge and has_tpm_unload and has_hidden_grub:
        record('UEFI Bootloader Resilience', 'PASS', 'grubx64.efi staged, fbx64.efi purged, rmmod tpm & Esc-revealed hidden GRUB verified')
    else:
        record(
            'UEFI Bootloader Resilience',
            'FAIL',
            f'has_grub_boot_stage={has_grub_boot_stage}, has_fb_purge={has_fb_purge}, '
            f'has_tpm_unload={has_tpm_unload}, has_hidden_grub={has_hidden_grub}',
        )
except Exception as e:
    record('UEFI Bootloader Resilience', 'FAIL', str(e))

# 11. LiveCD-Only Autologin & Installed OS Security Isolation Contract (v0.1.9)
try:
    sddm_autologin = 'files/system/etc/sddm.conf.d/autologin.conf'
    getty_autologin = 'files/system/etc/systemd/system/getty@tty1.service.d/autologin.conf'
    tuning_sh_path = 'files/scripts/02-system-tuning.sh'

    tuning_text = open(tuning_sh_path, 'r', encoding='utf-8').read()
    active_lines = [ln.strip() for ln in tuning_text.splitlines() if ln.strip() and not ln.strip().startswith('#')]

    no_static_sddm = not os.path.exists(sddm_autologin)
    no_static_getty = not os.path.exists(getty_autologin)
    no_blank_root = not any('passwd -d root' in ln for ln in active_lines)
    no_baked_liveuser = not any(re.search(r'\buseradd\b.*\bliveuser\b', ln) for ln in active_lines)
    has_locked_root = any('passwd -l root' in ln for ln in active_lines)
    has_livesys_kde = 'livesys_session="kde"' in tuning_text and 'livesys.service' in tuning_text
    has_live_only_extra = '/var/lib/livesys/livesys-session-extra' in tuning_text

    if (
        no_static_sddm
        and no_static_getty
        and no_blank_root
        and no_baked_liveuser
        and has_locked_root
        and has_livesys_kde
        and has_live_only_extra
    ):
        record(
            'LiveCD-Only Autologin Isolation',
            'PASS',
            'Static SDDM/TTY1 autologin & blank root removed; livesys handles rd.live.image sessions only',
        )
    else:
        record(
            'LiveCD-Only Autologin Isolation',
            'FAIL',
            f'no_static_sddm={no_static_sddm}, no_static_getty={no_static_getty}, '
            f'no_blank_root={no_blank_root}, no_baked_liveuser={no_baked_liveuser}, '
            f'has_locked_root={has_locked_root}, has_livesys_kde={has_livesys_kde}, '
            f'has_live_only_extra={has_live_only_extra}',
        )
except Exception as e:
    record('LiveCD-Only Autologin Isolation', 'FAIL', str(e))

# 12. Graphical Dual-Boot Installer & WebUI Browser Contract (v0.1.9 + v0.2.0 K-Installer)
try:
    pkgs_cfg = yaml.safe_load(open('recipes/packages.yml', 'r', encoding='utf-8'))
    install_pkgs = pkgs_cfg.get('install', {}).get('packages', [])
    remove_pkgs = pkgs_cfg.get('remove', {}).get('packages', [])
    desktop_launcher = 'files/system/etc/skel/Desktop/liveinst.desktop'
    just_file = 'files/system/usr/share/ublue-os/just/60-custom.just'

    has_anaconda = 'anaconda-live' in install_pkgs and 'partitionmanager' in install_pkgs
    has_firefox_webui = 'firefox' in install_pkgs and 'firefox' not in remove_pkgs
    launcher_text = open(desktop_launcher, encoding='utf-8').read() if os.path.exists(desktop_launcher) else ''
    has_launcher = 'Exec=/usr/bin/kushagra-installer' in launcher_text or 'Exec=liveinst' in launcher_text
    just_text = open(just_file, encoding='utf-8').read()
    has_just_recipe = 'install-to-disk:' in just_text and 'liveinst' in just_text

    if has_anaconda and has_firefox_webui and has_launcher and has_just_recipe:
        record(
            'Graphical Installer & WebUI Contract',
            'PASS',
            'anaconda-live, partitionmanager & firefox RPM in packages.yml; liveinst.desktop & ujust install-to-disk verified',
        )
    else:
        record(
            'Graphical Installer & WebUI Contract',
            'FAIL',
            f'has_anaconda={has_anaconda}, has_firefox_webui={has_firefox_webui}, '
            f'has_launcher={has_launcher}, has_just_recipe={has_just_recipe}',
        )
except Exception as e:
    record('Graphical Installer & WebUI Contract', 'FAIL', str(e))

# 13. Phase 2 Windows Compatibility & Storage Hygiene Contract
try:
    just_content = open('files/system/usr/share/ublue-os/just/60-custom.just', 'r', encoding='utf-8').read()
    has_gaming = 'install-gaming:' in just_content
    has_ubuntu_box = 'box-ubuntu:' in just_content
    has_clean_disk = 'clean-disk:' in just_content
    has_anti_cheat = 'check-anti-cheat:' in just_content

    if has_gaming and has_ubuntu_box and has_clean_disk and has_anti_cheat:
        record('Phase 2 Windows Compatibility Contract', 'PASS', 'install-gaming, box-ubuntu, clean-disk, and check-anti-cheat verified in 60-custom.just')
    else:
        record('Phase 2 Windows Compatibility Contract', 'FAIL', f'has_gaming={has_gaming}, has_ubuntu_box={has_ubuntu_box}, has_clean_disk={has_clean_disk}, has_anti_cheat={has_anti_cheat}')
except Exception as e:
    record('Phase 2 Windows Compatibility Contract', 'FAIL', str(e))

# 14. Custom Qt6/QML First-Boot Setup Wizard (kushagra-setup OOBE) Contract
try:
    pkgs_cfg = yaml.safe_load(open('recipes/packages.yml', 'r', encoding='utf-8'))
    recipe_cfg = yaml.safe_load(open('recipes/recipe.yml', 'r', encoding='utf-8'))
    install_pkgs = pkgs_cfg.get('install', {}).get('packages', [])
    systemd_mod = next((m for m in recipe_cfg.get('modules', []) if m.get('type') == 'systemd'), {})
    sys_enabled = systemd_mod.get('system', {}).get('enabled', [])
    sys_disabled = systemd_mod.get('system', {}).get('disabled', [])

    required_oobe_files = [
        'files/system/usr/bin/kushagra-setup',
        'files/system/usr/share/kushagra-os/oobe/main.py',
        'files/system/usr/share/kushagra-os/oobe/apply.py',
        'files/system/usr/share/kushagra-os/oobe/Main.qml',
        'files/system/usr/share/kushagra-os/oobe/kushagra-oobe-autostart.desktop',
        'files/system/usr/share/applications/kushagra-setup.desktop',
        'files/system/usr/share/kushagra-os/branding/logo-symbol.svg',
        'files/system/usr/libexec/kushagra-setup-bootutil',
        'files/system/usr/libexec/kushagra-oobe-apply',
        'files/system/usr/libexec/kushagra-apply-user-layout',
        'files/system/usr/lib/systemd/system/kushagra-oobe.service',
        'files/system/usr/lib/sysusers.d/kushagra-oobe.conf',
        'files/system/usr/lib/tmpfiles.d/kushagra-oobe.conf',
        'files/system/etc/polkit-1/rules.d/50-kushagra-oobe.rules',
        'files/system/usr/share/polkit-1/actions/org.kushagraos.oobe.policy',
    ]
    missing_oobe = [p for p in required_oobe_files if not os.path.exists(p)]

    # AST-parse OOBE Python scripts
    for py_path in [
        'files/system/usr/share/kushagra-os/oobe/main.py',
        'files/system/usr/share/kushagra-os/oobe/apply.py',
    ]:
        ast.parse(open(py_path, 'r', encoding='utf-8').read(), filename=py_path)

    # XML-parse Polkit policy
    ET.parse('files/system/usr/share/polkit-1/actions/org.kushagraos.oobe.policy')

    unit_text = open('files/system/usr/lib/systemd/system/kushagra-oobe.service', 'r', encoding='utf-8').read()
    tmpfiles_text = open('files/system/usr/lib/tmpfiles.d/kushagra-oobe.conf', 'r', encoding='utf-8').read()
    bootutil_text = open('files/system/usr/libexec/kushagra-setup-bootutil', 'r', encoding='utf-8').read()
    qml_text = open('files/system/usr/share/kushagra-os/oobe/Main.qml', 'r', encoding='utf-8').read()
    tuning_text = open('files/scripts/02-system-tuning.sh', 'r', encoding='utf-8').read()

    has_oobe_pkg = 'python3-pyqt6' in install_pkgs
    has_systemd_cfg = 'kushagra-oobe.service' in sys_enabled and 'plasma-setup.service' in sys_disabled
    has_unit_guards = (
        'ConditionPathExists=/var/lib/kushagra-oobe-pending' in unit_text
        and 'ConditionPathExists=!/etc/kushagra-oobe-done' in unit_text
        and 'ConditionKernelCommandLine=!rd.live.image' in unit_text
    )
    tmpfiles_active = [ln.strip() for ln in tmpfiles_text.splitlines() if ln.strip() and not ln.strip().startswith('#')]
    tuning_active = [ln.strip() for ln in tuning_text.splitlines() if ln.strip() and not ln.strip().startswith('#')]
    has_tmpfiles_var = (
        not any('kushagra-oobe-pending' in ln for ln in tmpfiles_active)
        and any('C /var/lib/livesys/livesys-session-extra' in ln for ln in tmpfiles_active)
    )
    has_uid_guard = (
        '$3 >= 1000' in bootutil_text
        and not any('kushagra-oobe-pending' in ln for ln in tuning_active)
    )
    oobe_main_txt = open('files/system/usr/share/kushagra-os/oobe/main.py', 'r', encoding='utf-8').read()
    oobe_apply_txt = open('files/system/usr/share/kushagra-os/oobe/apply.py', 'r', encoding='utf-8').read()
    layout_sh_txt = open('files/system/usr/libexec/kushagra-apply-user-layout', 'r', encoding='utf-8').read()
    has_v021_oobe = (
        'QQuickStyle.setStyle("Basic")' in oobe_main_txt
        and 'parent=engine' in oobe_main_txt
        and 'sync_fullscreen' in oobe_main_txt
        and '_is_real_screen' in oobe_main_txt
        and 'kushagra-oobe-handoff' in oobe_apply_txt
        and 'systemctl stop plasmalogin.service' in oobe_apply_txt
        and 'systemctl start plasmalogin.service' in oobe_apply_txt
        and 'qdbus-qt6' in layout_sh_txt
        and '(`wheel`)' not in qml_text
        and 'focusPolicy: Qt.NoFocus' in qml_text
        and 'visible: false' in qml_text
        and 'Qt.FramelessWindowHint' not in qml_text
        and 'Math.min(3' in qml_text
        and 'plasma-plasmashell.service' in tmpfiles_text
        and 'org.kde.discover.notifier.desktop' in tmpfiles_text
        and 'org.kde.panel' not in tmpfiles_text
    )
    has_all_screens = all(k in qml_text for k in ['en_IN', 'hi_IN', 'nmcli', 'Familiar Mode', 'Studio Mode', 'autoLoginSwitch', 'oobeBackend.finishSetup'])

    if not missing_oobe and has_oobe_pkg and has_systemd_cfg and has_unit_guards and has_tmpfiles_var and has_uid_guard and has_v021_oobe and has_all_screens:
        record(
            'Kushagra Setup OOBE Contract',
            'PASS',
            'Qt6/QML OOBE wizard, clean tmpfiles.d/kushagra-oobe.conf, systemd handoff, qdbus-qt6 layout switcher, and recipe settings verified',
        )
    else:
        record(
            'Kushagra Setup OOBE Contract',
            'FAIL',
            f'missing={missing_oobe}, has_oobe_pkg={has_oobe_pkg}, has_systemd_cfg={has_systemd_cfg}, '
            f'has_unit_guards={has_unit_guards}, has_tmpfiles_var={has_tmpfiles_var}, has_uid_guard={has_uid_guard}, '
            f'has_v021_oobe={has_v021_oobe}, has_all_screens={has_all_screens}',
        )
except Exception as e:
    record('Kushagra Setup OOBE Contract', 'FAIL', str(e))

# 15. Stage 1 Custom Qt6/QML K-Installer Contract (v0.5.0 offline native bootc + dual-boot)
try:
    required_installer_files = [
        'files/system/usr/bin/kushagra-installer',
        'files/system/usr/libexec/kushagra-installer-autostart',
        'files/system/usr/libexec/kushagra-installer-backend',
        'files/system/usr/libexec/kushagra-dualboot-grub',
        'files/system/etc/xdg/autostart/kushagra-installer-autostart.desktop',
        'files/system/usr/share/applications/kushagra-installer.desktop',
        'files/system/etc/polkit-1/rules.d/50-kushagra-installer.rules',
        'files/system/usr/share/polkit-1/actions/org.kushagraos.installer.policy',
        'files/system/usr/share/kushagra-os/installer/main.py',
        'files/system/usr/share/kushagra-os/installer/Main.qml',
        'files/system/usr/share/kushagra-os/installer/storage_probe.py',
        'files/system/usr/share/kushagra-os/installer/bootc_deploy.py',
    ]
    missing_inst = [p for p in required_installer_files if not os.path.exists(p)]

    inst_shell_true = []
    for py_path in [
        'files/system/usr/share/kushagra-os/installer/main.py',
        'files/system/usr/share/kushagra-os/installer/storage_probe.py',
        'files/system/usr/share/kushagra-os/installer/bootc_deploy.py',
        'files/system/usr/libexec/kushagra-installer-backend',
    ]:
        if os.path.exists(py_path):
            tree = ast.parse(open(py_path, 'r', encoding='utf-8').read(), filename=py_path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    for kw in node.keywords:
                        if kw.arg == 'shell' and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                            inst_shell_true.append(py_path)

    if os.path.exists('files/system/usr/share/polkit-1/actions/org.kushagraos.installer.policy'):
        ET.parse('files/system/usr/share/polkit-1/actions/org.kushagraos.installer.policy')

    autostart_sh = open('files/system/usr/libexec/kushagra-installer-autostart', 'r', encoding='utf-8').read()
    probe_txt = open('files/system/usr/share/kushagra-os/installer/storage_probe.py', 'r', encoding='utf-8').read()
    deploy_txt = open('files/system/usr/share/kushagra-os/installer/bootc_deploy.py', 'r', encoding='utf-8').read()
    backend_txt = open('files/system/usr/libexec/kushagra-installer-backend', 'r', encoding='utf-8').read()
    db_grub_txt = open('files/system/usr/libexec/kushagra-dualboot-grub', 'r', encoding='utf-8').read()
    inst_main_txt = open('files/system/usr/share/kushagra-os/installer/main.py', 'r', encoding='utf-8').read()
    inst_qml = open('files/system/usr/share/kushagra-os/installer/Main.qml', 'r', encoding='utf-8').read()
    livesys_extra = open('files/system/usr/share/kushagra-os/livesys/livesys-session-extra', 'r', encoding='utf-8').read()

    has_live_gate = 'rd.live.image' in autostart_sh and 'liveuser' in autostart_sh
    has_safety_locks = (
        'WIN_FSTYPES' in probe_txt
        and 'ESP_PARTTYPES' in probe_txt
        and 'c12a7328-f81f-11d2-ba4b-00a0c93ec93b' in probe_txt
        and 'c12a7328-f81f-11d2-ba4b-00a0c93ec3b3' not in probe_txt
        and 'MIN_ESP_FREE_MIB = 35' in probe_txt
        and 'detect_live_disk_paths' in probe_txt
        and 'os.path.basename' in probe_txt
        and 'needsInitGpt' in probe_txt
        and '"startBytes"' in probe_txt
    )
    has_bootc_deploy = (
        all(tok in deploy_txt for tok in [
            'OCI_SOURCE_DIR = "/run/initramfs/live/kushagra-oci"',
            '--source-imgref=oci:',
            '--enforce-container-sigpolicy',
            '--skip-fetch-check',
            '--root-mount-spec=UUID=',
            '--bootloader=grub',
            '--stateroot=default',
            '--skip-finalize',
            'label=type:unconfined_t',
            '--rootfs',
            '/sys/fs/selinux:/sys/fs/selinux',
            '/sys/firmware/efi/efivars:/sys/firmware/efi/efivars',
            'bootc',
            'finalize',
            'compress=zstd:1',
            'EFI_BACKUP_DIR',
            '_sha256_file',
            'kushagra-oobe-pending',
        ])
        and '/:O' not in deploy_txt
        and 'bootc_deploy.deploy_system' in backend_txt
        and '--cmdline' not in backend_txt
    )
    has_dualboot_grub = all(tok in db_grub_txt for tok in [
        'custom.cfg',
        'bootmgfw.efi',
        'timeout_style=menu',
        'timeout=4',
        'timeout_style=hidden',
        'timeout=1',
        'chainloader',
        'Windows Boot Manager',
        'chmod 0644',
    ])
    has_qml_screens = (
        all(k in inst_qml for k in ['Install Kushagra OS', 'Try Live Desktop', 'installLogsText', 'espLowSpace', 'legacyRamAdvisory'])
        and 'visible: false' in inst_qml
        and 'Qt.FramelessWindowHint' not in inst_qml
        and 'sync_fullscreen' in inst_main_txt
        and '_is_real_screen' in inst_main_txt
        and 'LEGACY_RAM_THRESHOLD_KIB = 7549747' in inst_main_txt
    )
    has_livesys_kiosk = (
        'kushagra-installer.desktop' in livesys_extra
        and 'org.kde.plasma-welcome.desktop' in livesys_extra
        and 'chown -R liveuser:liveuser /home/liveuser' in livesys_extra
        and 'plasma-welcomerc' in livesys_extra
        and 'drkonqi' in livesys_extra
        and 'kscreenlockerrc' in livesys_extra
        and 'plasma-powerdevil.service' in livesys_extra
    )

    if not missing_inst and not inst_shell_true and has_live_gate and has_safety_locks and has_bootc_deploy and has_dualboot_grub and has_qml_screens and has_livesys_kiosk:
        record(
            'Kushagra K-Installer Stage 1 Contract',
            'PASS',
            'Offline native bootc deploy_system, Windows EFI SHA256 RAM guard, update-safe GRUB custom.cfg & <8GB advisory verified',
        )
    else:
        record(
            'Kushagra K-Installer Stage 1 Contract',
            'FAIL',
            f'missing={missing_inst}, shell_true={inst_shell_true}, has_live_gate={has_live_gate}, '
            f'has_safety_locks={has_safety_locks}, has_bootc_deploy={has_bootc_deploy}, '
            f'has_dualboot_grub={has_dualboot_grub}, has_qml_screens={has_qml_screens}, has_livesys_kiosk={has_livesys_kiosk}',
        )
except Exception as e:
    record('Kushagra K-Installer Stage 1 Contract', 'FAIL', str(e))

# 16. Universal App Layer Contract (Bazaar, WinRun .exe/.msi, Smart Waydroid ARM)
try:
    flatpaks_cfg = yaml.safe_load(open('recipes/flatpaks.yml', 'r', encoding='utf-8'))
    flatpak_installs = []
    for cfg in flatpaks_cfg.get('configurations', []):
        flatpak_installs.extend(cfg.get('install', []))

    has_bazaar = 'io.github.kolunmi.Bazaar' in flatpak_installs
    has_bottles = 'com.usebottles.bottles' in flatpak_installs

    winrun_files = [
        'files/system/usr/bin/kushagra-winrun',
        'files/system/usr/share/kushagra-os/winrun/main.py',
        'files/system/usr/share/applications/kushagra-winrun.desktop',
        'files/system/etc/xdg/mimeapps.list',
    ]
    missing_winrun = [p for p in winrun_files if not os.path.exists(p)]
    if os.path.exists('files/system/usr/share/kushagra-os/winrun/main.py'):
        ast.parse(open('files/system/usr/share/kushagra-os/winrun/main.py', 'r', encoding='utf-8').read())

    winrun_desktop = open('files/system/usr/share/applications/kushagra-winrun.desktop', 'r', encoding='utf-8').read()
    mimeapps_txt = open('files/system/etc/xdg/mimeapps.list', 'r', encoding='utf-8').read()
    just_txt = open('files/system/usr/share/ublue-os/just/60-custom.just', 'r', encoding='utf-8').read()
    tuning_txt = open('files/scripts/02-system-tuning.sh', 'r', encoding='utf-8').read()

    has_mime = (
        'application/x-ms-dos-executable' in winrun_desktop
        and 'application/x-msi' in winrun_desktop
        and 'kushagra-winrun.desktop' in mimeapps_txt
        and 'update-desktop-database' in tuning_txt
        and 'update-mime-database' in tuning_txt
    )
    has_waydroid_smart = (
        'GenuineIntel' in just_txt
        and 'AuthenticAMD' in just_txt
        and 'libhoudini' in just_txt
        and 'libndk' in just_txt
        and 'persist.waydroid.multi_windows' in just_txt
        and 'MEETS_STRONG_INTEGRITY' in just_txt
    )

    if has_bazaar and has_bottles and not missing_winrun and has_mime and has_waydroid_smart:
        record(
            'Universal App Layer Contract',
            'PASS',
            'Bazaar Flathub store, WinRun .exe/.msi MIME handler, and Intel/AMD ARM-aware Waydroid setup verified',
        )
    else:
        record(
            'Universal App Layer Contract',
            'FAIL',
            f'has_bazaar={has_bazaar}, has_bottles={has_bottles}, missing_winrun={missing_winrun}, has_mime={has_mime}, has_waydroid_smart={has_waydroid_smart}',
        )
except Exception as e:
    record('Universal App Layer Contract', 'FAIL', str(e))

# 17. v0.2.1 LiveCD Systemd Guards, Bottles/Gaming & Branding Contract
try:
    sf_svc = open('files/system/etc/systemd/system/system-flatpak-setup.service.d/10-skip-livecd.conf', 'r', encoding='utf-8').read()
    sf_tmr = open('files/system/etc/systemd/system/system-flatpak-setup.timer.d/10-skip-livecd.conf', 'r', encoding='utf-8').read()
    bl_svc = open('files/system/etc/systemd/system/bootloader-update.service.d/10-kushagra-live-guard.conf', 'r', encoding='utf-8').read()
    winrun_py = open('files/system/usr/share/kushagra-os/winrun/main.py', 'r', encoding='utf-8').read()
    just_cfg = open('files/system/usr/share/ublue-os/just/60-custom.just', 'r', encoding='utf-8').read()
    recipe_raw = open('recipes/recipe.yml', 'r', encoding='utf-8').read()
    issue_raw = open('files/system/etc/issue.net', 'r', encoding='utf-8').read()

    has_live_guards = (
        'ConditionKernelCommandLine=!rd.live.image' in sf_svc
        and 'ConditionKernelCommandLine=!rd.live.image' in sf_tmr
        and 'ConditionKernelCommandLine=!rd.live.image' in bl_svc
        and 'ConditionPathExists=/sysroot/ostree' in bl_svc
    )
    has_app_fixes = (
        'find_existing_bottle' in winrun_py
        and 'flatpak install --system' in just_cfg
    )
    cfg_issue_raw = open('config/issue.net', 'r', encoding='utf-8').read()
    has_v050_branding = (
        'v0.5.0' in recipe_raw
        and 'v0.1 Prototype' not in recipe_raw
        and 'v0.5.0' in issue_raw
        and 'v0.1 Prototype' not in issue_raw
        and 'v0.5.0' in cfg_issue_raw
    )

    if has_live_guards and has_app_fixes and has_v050_branding:
        record(
            'v0.5.0 LiveCD Guards & Branding Contract',
            'PASS',
            'LiveCD flatpak/bootloader guards, Bottles/system gaming fixes, and v0.5.0 branding verified',
        )
    else:
        record(
            'v0.5.0 LiveCD Guards & Branding Contract',
            'FAIL',
            f'has_live_guards={has_live_guards}, has_app_fixes={has_app_fixes}, has_v050_branding={has_v050_branding}',
        )
except Exception as e:
    record('v0.5.0 LiveCD Guards & Branding Contract', 'FAIL', str(e))

# 18. Zero-Text Silent OEM Boot, Kushagra Plymouth Theme & Flicker-Free Kiosk Handoff Contract
try:
    import tomllib

    recipe_cfg = yaml.safe_load(open('recipes/recipe.yml', 'r', encoding='utf-8'))
    modules = recipe_cfg.get('modules', [])
    script_idx = next((i for i, m in enumerate(modules) if m.get('type') == 'script'), -1)
    initramfs_idx = next((i for i, m in enumerate(modules) if m.get('type') == 'initramfs'), -1)
    script_list = modules[script_idx].get('scripts', []) if script_idx >= 0 else []
    has_plymouth_hook_order = (
        0 <= script_idx < initramfs_idx
        and '03-configure-plymouth-theme.sh' in script_list
        and os.path.exists('files/scripts/03-configure-plymouth-theme.sh')
    )

    ply_conf = open('files/system/etc/plymouth/plymouthd.conf', 'r', encoding='utf-8').read()
    ply_theme = open('files/system/usr/share/plymouth/themes/kushagra/kushagra.plymouth', 'r', encoding='utf-8').read()
    has_plymouth_theme = (
        'Theme=kushagra' in ply_conf
        and 'UseSimpledrmNoLuks=1' in ply_conf
        and 'ModuleName=two-step' in ply_theme
        and 'UseFirmwareBackground=true' in ply_theme
        and 'ImageDir=/usr/share/plymouth/themes/kushagra' in ply_theme
        and os.path.exists('files/system/usr/share/plymouth/themes/kushagra/watermark.png')
        and os.path.exists('files/system/usr/share/pixmaps/kushagra-logo.png')
    )

    kargs_toml = tomllib.loads(open('files/system/usr/lib/bootc/kargs.d/10-kushagra-boot.toml', 'r', encoding='utf-8').read())
    kargs_list = kargs_toml.get('kargs', [])
    has_bootc_kargs = (
        all(k in kargs_list for k in ['quiet', 'splash', 'rhgb', 'loglevel=3', 'systemd.show_status=false', 'vt.global_cursor_default=0'])
        and all('console=ttyS0' not in k for k in kargs_list)
    )

    livesys_txt = open('files/system/usr/share/kushagra-os/livesys/livesys-session-extra', 'r', encoding='utf-8').read()
    inst_main = open('files/system/usr/share/kushagra-os/installer/main.py', 'r', encoding='utf-8').read()
    inst_qml = open('files/system/usr/share/kushagra-os/installer/Main.qml', 'r', encoding='utf-8').read()
    has_stage1_kiosk = (
        os.path.exists('files/system/usr/lib/systemd/user/kushagra-installer.service')
        and 'plasma-plasmashell.service' in livesys_txt
        and 'plasma-ksplash.service' in livesys_txt
        and 'plasma-wallpaper.service' in livesys_txt
        and 'kushagra-installer.service' in livesys_txt
        and 'setVisibility(QWindow.Visibility.Windowed)' not in inst_main
        and 'RestoreDesktopWorker' in inst_main
        and 'launchingDesktop' in inst_qml
    )

    tmpfiles_txt = open('files/system/usr/lib/tmpfiles.d/kushagra-oobe.conf', 'r', encoding='utf-8').read()
    oobe_main = open('files/system/usr/share/kushagra-os/oobe/main.py', 'r', encoding='utf-8').read()
    has_stage2_kiosk = (
        os.path.exists('files/system/usr/lib/systemd/user/kushagra-oobe-ui.service')
        and os.path.exists('files/system/etc/skel/.config/plasma-welcomerc')
        and os.path.exists('files/system/etc/skel/.config/ksplashrc')
        and 'plasma-ksplash.service' in tmpfiles_txt
        and 'plasma-wallpaper.service' in tmpfiles_txt
        and 'kushagra-oobe-ui.service' in tmpfiles_txt
        and 'setVisibility(QWindow.Visibility.Windowed)' not in oobe_main
        and 'SIGTERM' in oobe_main
        and '_install_signal_handlers' in oobe_main
    )

    if has_plymouth_hook_order and has_plymouth_theme and has_bootc_kargs and has_stage1_kiosk and has_stage2_kiosk:
        record(
            'Zero-Text Silent OEM Boot & Kiosk Handoff Contract',
            'PASS',
            'Plymouth kushagra theme before initramfs, bootc kargs.d, Stage 1 & Stage 2 zero-flash kiosk verified',
        )
    else:
        record(
            'Zero-Text Silent OEM Boot & Kiosk Handoff Contract',
            'FAIL',
            f'has_plymouth_hook_order={has_plymouth_hook_order}, has_plymouth_theme={has_plymouth_theme}, '
            f'has_bootc_kargs={has_bootc_kargs}, has_stage1_kiosk={has_stage1_kiosk}, has_stage2_kiosk={has_stage2_kiosk}',
        )
except Exception as e:
    record('Zero-Text Silent OEM Boot & Kiosk Handoff Contract', 'FAIL', str(e))

# 19. Plasma 6.8.3 Zero-Glitch UX, Windows Shortcuts & .apk Handler Contract
try:
    xdg_kwin = open('files/system/etc/xdg/kwinrc', 'r', encoding='utf-8').read()
    skel_kwin = open('files/system/etc/skel/.config/kwinrc', 'r', encoding='utf-8').read()
    livesys_v3 = open('files/system/usr/share/kushagra-os/livesys/livesys-session-extra', 'r', encoding='utf-8').read()
    tmp_oobe_v3 = open('files/system/usr/lib/tmpfiles.d/kushagra-oobe.conf', 'r', encoding='utf-8').read()
    fcitx_prof = open('files/system/etc/skel/.config/fcitx5/profile', 'r', encoding='utf-8').read()

    has_ime_lock = all(
        'InputMethod[$i]=/usr/share/applications/fcitx5-wayland-launcher.desktop' in txt
        for txt in (xdg_kwin, skel_kwin, livesys_v3, tmp_oobe_v3)
    ) and 'keyboard-in-eng' in fcitx_prof and 'm17n_hi_itrans' in fcitx_prof

    welcome_autostart = open('files/system/etc/xdg/autostart/org.kde.plasma-welcome.desktop', 'r', encoding='utf-8').read()
    kded6rc_txt = open('files/system/etc/xdg/kded6rc', 'r', encoding='utf-8').read()
    xdg_welcome_rc = open('files/system/etc/xdg/plasma-welcomerc', 'r', encoding='utf-8').read()
    skel_welcome_rc = open('files/system/etc/skel/.config/plasma-welcomerc', 'r', encoding='utf-8').read()
    has_welcome_suppressed = (
        'Hidden=true' in welcome_autostart
        and '[Module-plasma_welcome]' in kded6rc_txt
        and 'autoload=false' in kded6rc_txt
        and 'ShouldShow=false' in xdg_welcome_rc
        and 'ShouldShow=false' in skel_welcome_rc
    )

    xdg_sc = open('files/system/etc/xdg/kglobalshortcutsrc', 'r', encoding='utf-8').read()
    skel_sc = open('files/system/etc/skel/.config/kglobalshortcutsrc', 'r', encoding='utf-8').read()
    layout_apply_v3 = open('files/system/usr/libexec/kushagra-apply-user-layout', 'r', encoding='utf-8').read()
    required_sc = [
        'Edit Tiles=Meta+T',
        'Show Desktop=Meta+D',
        'show-on-mouse-pos=Meta+V',
        'org.kde.plasma-systemmonitor.desktop',
        'Ctrl+Shift+Esc',
        'org.kde.konsole.desktop',
        'Ctrl+Alt+T',
        'org.kde.dolphin.desktop',
        'Meta+E',
        'org.kde.krunner.desktop',
        'Alt+Space',
    ]
    has_shortcuts = (
        all(tok in xdg_sc and tok in skel_sc for tok in required_sc)
        and 'Edit Tiles' in layout_apply_v3
        and 'Ctrl+Alt+T' in layout_apply_v3
        and 'Ctrl+Shift+Esc' in layout_apply_v3
    )

    apk_py_path = 'files/system/usr/share/kushagra-os/apkrun/main.py'
    ast.parse(open(apk_py_path, 'r', encoding='utf-8').read(), filename=apk_py_path)
    apk_py = open(apk_py_path, 'r', encoding='utf-8').read()
    apk_desk = open('files/system/usr/share/applications/kushagra-apkrun.desktop', 'r', encoding='utf-8').read()
    mime_v3 = open('files/system/etc/xdg/mimeapps.list', 'r', encoding='utf-8').read()
    has_apk = (
        os.path.exists('files/system/usr/bin/kushagra-apkrun')
        and 'rd.live.image' in apk_py
        and 'REMOTE_SCHEMES' in apk_py
        and 'waydroid app install' in apk_py
        and 'MEETS_STRONG_INTEGRITY' in apk_py
        and 'application/vnd.android.package-archive' in apk_desk
        and 'application/vnd.android.package-archive=kushagra-apkrun.desktop' in mime_v3
    )

    if has_ime_lock and has_welcome_suppressed and has_shortcuts and has_apk:
        record(
            'Plasma 6.8.3 UX, Shortcuts & APK Contract',
            'PASS',
            'InputMethod[$i] lock, Welcome Center suppression, Edit Tiles=Meta+T + Ctrl+Alt+T + Win shortcuts, and kushagra-apkrun verified',
        )
    else:
        record(
            'Plasma 6.8.3 UX, Shortcuts & APK Contract',
            'FAIL',
            f'has_ime_lock={has_ime_lock}, has_welcome_suppressed={has_welcome_suppressed}, has_shortcuts={has_shortcuts}, has_apk={has_apk}',
        )
except Exception as e:
    record('Plasma 6.8.3 UX, Shortcuts & APK Contract', 'FAIL', str(e))

# 20. Kushagra Kavach Security Suite Contract (Rule #8/#9)
try:
    pkgs_cfg_v3 = yaml.safe_load(open('recipes/packages.yml', 'r', encoding='utf-8'))
    pkgs_v3 = pkgs_cfg_v3.get('install', {}).get('packages', [])
    recipe_cfg_v3 = yaml.safe_load(open('recipes/recipe.yml', 'r', encoding='utf-8'))
    sys_enabled_v3 = next((m for m in recipe_cfg_v3.get('modules', []) if m.get('type') == 'systemd'), {}).get('system', {}).get('enabled', [])

    resolved_txt = open('files/system/etc/systemd/resolved.conf.d/10-dot-opportunistic.conf', 'r', encoding='utf-8').read()
    resolved_active = [ln.strip() for ln in resolved_txt.splitlines() if ln.strip() and not ln.strip().startswith('#')]
    has_quad9 = (
        any(ln.startswith('DNS=') and '9.9.9.9#dns.quad9.net' in ln and '149.112.112.112#dns.quad9.net' in ln for ln in resolved_active)
        and any(ln == 'DNSOverTLS=opportunistic' for ln in resolved_active)
        and not any('.10' in ln or 'DNSOverTLS=yes' in ln for ln in resolved_active)
        and os.path.exists('files/system/usr/libexec/kushagra-kavach-dns')
    )

    usb_safe_txt = open('files/system/etc/systemd/system/usbguard.service.d/10-kushagra-safe.conf', 'r', encoding='utf-8').read()
    usb_setup_txt = open('files/system/usr/libexec/kushagra-usbguard-setup', 'r', encoding='utf-8').read()
    polkit_kavach = open('files/system/etc/polkit-1/rules.d/50-kushagra-kavach.rules', 'r', encoding='utf-8').read()
    has_usbguard_safe = (
        all(p in pkgs_v3 for p in ['usbguard', 'usbguard-selinux', 'usbguard-dbus', 'usbguard-notifier'])
        and 'usbguard.service' not in sys_enabled_v3
        and 'ConditionKernelCommandLine=!rd.live.image' in usb_safe_txt
        and 'ConditionFileNotEmpty=/etc/usbguard/rules.conf' in usb_safe_txt
        and 'generate-policy' in usb_setup_txt
        and 'read -r -t 15' in usb_setup_txt
        and 'org.usbguard' in polkit_kavach
    )

    scan_sh = open('files/system/usr/bin/kushagra-kavach-scan', 'r', encoding='utf-8').read()
    kio_desk = open('files/system/usr/share/kio/servicemenus/kushagra-kavach-scan.desktop', 'r', encoding='utf-8').read()
    kavach_tmp = open('files/system/usr/lib/tmpfiles.d/kushagra-kavach.conf', 'r', encoding='utf-8').read()
    tuning_v3 = open('files/scripts/02-system-tuning.sh', 'r', encoding='utf-8').read()
    has_clamav_safe = (
        'clamav' in pkgs_v3
        and 'clamav-freshclam' in pkgs_v3
        and 'clamav-data' not in pkgs_v3
        and 'clamd' not in pkgs_v3
        and 'freshclam' in scan_sh
        and 'clamscan' in scan_sh
        and 'Scan with Kushagra Kavach' in kio_desk
        and '/var/lib/clamav' in kavach_tmp
        and 'freshclam.conf' in tuning_v3
    )

    mirror_sh = open('files/system/usr/libexec/kushagra-lan-mirror', 'r', encoding='utf-8').read()
    just_v3 = open('files/system/usr/share/ublue-os/just/60-custom.just', 'r', encoding='utf-8').read()
    has_mirror_and_just = (
        '90-kushagra-lan-mirror.conf' in mirror_sh
        and 'digest-only' in mirror_sh
        and all(r in just_v3 for r in ['kavach-dns', 'scan-path', 'setup-usbguard', 'setup-lan-mirror'])
    )

    if has_quad9 and has_usbguard_safe and has_clamav_safe and has_mirror_and_just:
        record(
            'Kushagra Kavach Security Suite Contract',
            'PASS',
            'Quad9 opportunistic DoT, HID-safe opt-in USBGuard, on-demand ClamAV (zero clamd), 90-kushagra-lan-mirror.conf & ujust verified',
        )
    else:
        record(
            'Kushagra Kavach Security Suite Contract',
            'FAIL',
            f'has_quad9={has_quad9}, has_usbguard_safe={has_usbguard_safe}, has_clamav_safe={has_clamav_safe}, has_mirror_and_just={has_mirror_and_just}',
        )
except Exception as e:
    record('Kushagra Kavach Security Suite Contract', 'FAIL', str(e))

# 21. Safe Liquid Glass UI Contract (Plasma 6.8.3)
try:
    recipe_cfg_v4 = yaml.safe_load(open('recipes/recipe.yml', 'r', encoding='utf-8'))
    modules_v4 = recipe_cfg_v4.get('modules', [])
    script_idx_v4 = next((i for i, m in enumerate(modules_v4) if m.get('type') == 'script'), -1)
    initramfs_idx_v4 = next((i for i, m in enumerate(modules_v4) if m.get('type') == 'initramfs'), -1)
    script_list_v4 = modules_v4[script_idx_v4].get('scripts', []) if script_idx_v4 >= 0 else []

    glass_build_sh = open('files/scripts/04-build-kwin-glass.sh', 'r', encoding='utf-8').read()
    glass_toggle_sh_txt = open('files/system/usr/bin/kushagra-glass-toggle', 'r', encoding='utf-8').read()
    has_glass_build = (
        0 <= script_idx_v4 < initramfs_idx_v4
        and '04-build-kwin-glass.sh' in script_list_v4
        and 'kwin-effects-better-blur-dx' not in glass_build_sh
        and all(dep in glass_build_sh for dep in [
            'kwin-devel',
            'kf6-kguiaddons-devel',
            'kdecoration-devel',
            'libplasma-devel',
            'qt6-qtbase-private-devel',
            'plasma-wayland-protocols-devel',
            'libdrm-devel',
            'mesa-libgbm-devel',
            'vulkan-loader-devel',
        ])
        and 'dnf5 remove' in glass_build_sh
        and 'jq|' in glass_build_sh
        and 'copr enable' not in glass_build_sh.lower()
        and 'copr.fedorainfracloud.org' not in glass_build_sh.lower()
        and 'stock-blur-fallback' in glass_build_sh
        and 'kwinrc_set "Plugins" "blurEnabled" "false"' in glass_toggle_sh_txt
        and 'reconfigureEffect' in glass_toggle_sh_txt
    )

    kdeglobals_txt = open('files/system/etc/xdg/kdeglobals', 'r', encoding='utf-8').read()
    kwinrules_txt = open('files/system/etc/xdg/kwinrulesrc', 'r', encoding='utf-8').read()
    has_palette_and_rules = (
        os.path.exists('files/system/usr/share/color-schemes/KushagraGlassDark.colors')
        and os.path.exists('files/system/usr/share/color-schemes/KushagraGlassLight.colors')
        and 'ColorScheme=KushagraGlassDark' in kdeglobals_txt
        and 'union' not in kdeglobals_txt.lower()
        and 'opacityactive=100' in kwinrules_txt
        and 'opacityactiverule=2' in kwinrules_txt
    )

    glass_guard_sh = open('files/system/usr/bin/kushagra-glass-guard', 'r', encoding='utf-8').read()
    glass_toggle_sh = open('files/system/usr/bin/kushagra-glass-toggle', 'r', encoding='utf-8').read()
    glass_unit_txt = open('files/system/usr/lib/systemd/user/kushagra-glass-guard.service', 'r', encoding='utf-8').read()
    live_ply_gen = open('files/system/usr/lib/systemd/system-generators/kushagra-live-plymouth-generator', 'r', encoding='utf-8').read()
    just_v4_1 = open('files/system/usr/share/ublue-os/just/60-custom.just', 'r', encoding='utf-8').read()
    has_guard_and_toggle = (
        '3670016' in glass_guard_sh
        and '4718592' not in glass_guard_sh
        and '-lt "${LOW_RAM_THRESHOLD_KB}"' in glass_guard_sh
        and 'llvmpipe' in glass_guard_sh
        and 'lavapipe' in glass_guard_sh
        and 'BlurStrength' in glass_toggle_sh
        and 'ExecStart=/usr/bin/kushagra-glass-guard' in glass_unit_txt
        and 'plasmalogin.service.d' in live_ply_gen
        and 'plymouth.conf' in live_ply_gen
        and 'rd.live.image' in live_ply_gen
        and 'toggle-glass' in just_v4_1
    )

    if has_glass_build and has_palette_and_rules and has_guard_and_toggle:
        record(
            'Safe Liquid Glass UI Contract',
            'PASS',
            'Ephemeral 6.8.3 build, opaque CSD kwinrulesrc, Dark/Light palettes, and <3.5 GiB emergency RAM + sw-GPU guard verified',
        )
    else:
        record(
            'Safe Liquid Glass UI Contract',
            'FAIL',
            f'has_glass_build={has_glass_build}, has_palette_and_rules={has_palette_and_rules}, has_guard_and_toggle={has_guard_and_toggle}',
        )
except Exception as e:
    record('Safe Liquid Glass UI Contract', 'FAIL', str(e))

# 22. K-AI Hybrid Engine, Profiler, Broker, Drawer, KRunner & OCR Contract
try:
    import json as _json

    pkgs_cfg_v4 = yaml.safe_load(open('recipes/packages.yml', 'r', encoding='utf-8'))
    pkgs_v4 = pkgs_cfg_v4.get('install', {}).get('packages', [])
    recipe_cfg_k4 = yaml.safe_load(open('recipes/recipe.yml', 'r', encoding='utf-8'))
    modules_k4 = recipe_cfg_k4.get('modules', [])
    script_idx_k4 = next((i for i, m in enumerate(modules_k4) if m.get('type') == 'script'), -1)
    initramfs_idx_k4 = next((i for i, m in enumerate(modules_k4) if m.get('type') == 'initramfs'), -1)
    script_list_k4 = modules_k4[script_idx_k4].get('scripts', []) if script_idx_k4 >= 0 else []
    llama_build_path = 'files/scripts/05-build-llama-vulkan.sh'
    llama_build_sh = open(llama_build_path, 'r', encoding='utf-8').read() if os.path.exists(llama_build_path) else ''
    has_kai_pkgs = (
        'llama-cpp' not in pkgs_v4
        and all(
            p in pkgs_v4
            for p in ['vulkan-loader', 'vulkan-tools', 'libgomp', 'tesseract', 'tesseract-langpack-hin', 'spectacle', 'wl-clipboard', 'python3-gobject']
        )
        and 0 <= script_idx_k4 < initramfs_idx_k4
        and '05-build-llama-vulkan.sh' in script_list_k4
        and all(tok in llama_build_sh for tok in [
            'LLAMA_TAG="b12823"',
            '-DGGML_VULKAN=ON',
            '-DGGML_NATIVE=OFF',
            '-DGGML_HIP=OFF',
            '-DGGML_CUDA=OFF',
            '-DLLAMA_CURL=OFF',
            '-DLLAMA_BUILD_TESTS=OFF',
            '-DLLAMA_BUILD_EXAMPLES=OFF',
            '-DBUILD_SHARED_LIBS=ON',
            '--target llama-server',
            'spirv-headers-devel',
            'glslc',
            '/usr/bin/llama-server',
            'strip --strip-unneeded',
            'dnf5 remove',
            'jq|',
            'vulkan-loader',
            '--list-devices',
        ])
        and 'copr enable' not in llama_build_sh.lower()
        and 'copr.fedorainfracloud.org' not in llama_build_sh.lower()
    )

    kai_py_files = [
        'files/system/usr/bin/k-ai-detect',
        'files/system/usr/bin/k-ai-engine',
        'files/system/usr/libexec/k-ai-broker',
        'files/system/usr/libexec/k-ai-krunner',
        'files/system/usr/bin/k-ai-followalong',
        'files/system/usr/bin/k-ai-ocr',
        'files/system/usr/share/kushagra-os/kai/main.py',
    ]
    shell_true_hits = []
    for ppath in kai_py_files:
        tree = ast.parse(open(ppath, 'r', encoding='utf-8').read(), filename=ppath)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if kw.arg == 'shell' and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        shell_true_hits.append(ppath)

    detect_py = open('files/system/usr/bin/k-ai-detect', 'r', encoding='utf-8').read()
    engine_py = open('files/system/usr/bin/k-ai-engine', 'r', encoding='utf-8').read()
    tuning_v4 = open('files/scripts/02-system-tuning.sh', 'r', encoding='utf-8').read()
    has_core_engine = (
        'TIER1_MAX_RAM_GIB' in detect_py
        and 'TIER2_MAX_RAM_GIB' in detect_py
        and 'HYBRID_VRAM_MAX_GIB' in detect_py
        and 'DEFAULT_IDLE_TIMEOUT = 300' in engine_py
        and os.path.exists('files/system/usr/lib/systemd/user/k-ai-engine.socket')
        and os.path.exists('files/system/usr/lib/systemd/user/k-ai-engine.service')
        and 'systemctl --global enable k-ai-engine.socket' in tuning_v4
        and 'systemctl --global disable k-ai-engine.service' in tuning_v4
    )

    actions_cfg = _json.loads(open('files/system/usr/share/kushagra-os/kai/actions.json', 'r', encoding='utf-8').read())
    actions_map = actions_cfg.get('actions', {})
    required_actions = ['kavach_dns', 'glass_toggle', 'layout_switch', 'kavach_scan', 'resolve_convert', 'health_report', 'reboot_windows']
    broker_py = open('files/system/usr/libexec/k-ai-broker', 'r', encoding='utf-8').read()
    polkit_kai = open('files/system/etc/polkit-1/rules.d/50-kushagra-kai.rules', 'r', encoding='utf-8').read()
    has_broker_policy = (
        all(a in actions_map for a in required_actions)
        and '--approved' in broker_py
        and 'os.path.realpath' in broker_py
        and 'os.path.commonpath' in broker_py
        and 'audit.jsonl' in broker_py
        and 'org.freedesktop.policykit.exec' in polkit_kai
    )

    krunner_py = open('files/system/usr/libexec/k-ai-krunner', 'r', encoding='utf-8').read()
    krunner_desk = open('files/system/usr/share/krunner/dbusplugins/k-ai-krunner.desktop', 'r', encoding='utf-8').read()
    krunner_dbus = open('files/system/usr/share/dbus-1/services/org.kushagraos.KAI.Runner.service', 'r', encoding='utf-8').read()
    ocr_py = open('files/system/usr/bin/k-ai-ocr', 'r', encoding='utf-8').read()
    xdg_sc_v4 = open('files/system/etc/xdg/kglobalshortcutsrc', 'r', encoding='utf-8').read()
    skel_sc_v4 = open('files/system/etc/skel/.config/kglobalshortcutsrc', 'r', encoding='utf-8').read()
    apply_layout_v4 = open('files/system/usr/libexec/kushagra-apply-user-layout', 'r', encoding='utf-8').read()
    has_ui_and_ux = (
        os.path.exists('files/system/usr/share/kushagra-os/kai/Main.qml')
        and os.path.exists('files/system/usr/bin/k-ai-drawer')
        and os.path.exists('files/system/usr/share/applications/k-ai-drawer.desktop')
        and os.path.exists('files/system/usr/share/applications/k-ai-followalong.desktop')
        and os.path.exists('files/system/usr/share/applications/k-ai-ocr.desktop')
        and 'Variant("(a(sssida{sv}))"' in krunner_py
        and 'Variant("(a(sss))"' in krunner_py
        and 'org.kushagraos.KAI.Runner' in krunner_desk
        and 'Exec=/usr/libexec/k-ai-krunner' in krunner_dbus
        and '_shred_file' in ocr_py
        and 'k-ai-drawer.desktop' in xdg_sc_v4 and 'Meta+Space' in xdg_sc_v4
        and 'k-ai-followalong.desktop' in xdg_sc_v4 and 'Ctrl+Shift+A' in xdg_sc_v4
        and 'k-ai-drawer.desktop' in skel_sc_v4 and 'k-ai-followalong.desktop' in skel_sc_v4
        and 'k-ai-drawer.desktop' in apply_layout_v4 and 'k-ai-followalong.desktop' in apply_layout_v4
        and 'Edit Tiles=Meta+T' in xdg_sc_v4
    )

    if has_kai_pkgs and not shell_true_hits and has_core_engine and has_broker_policy and has_ui_and_ux:
        record(
            'K-AI Hybrid Engine, Broker, UI, KRunner & OCR Contract',
            'PASS',
            '3-tier profiler, 0MB lazy socket/300s unload, allowlisted broker, GLib.Variant KRunner, FollowAlong/OCR & shortcuts verified',
        )
    else:
        record(
            'K-AI Hybrid Engine, Broker, UI, KRunner & OCR Contract',
            'FAIL',
            f'has_kai_pkgs={has_kai_pkgs}, shell_true_hits={shell_true_hits}, has_core_engine={has_core_engine}, has_broker_policy={has_broker_policy}, has_ui_and_ux={has_ui_and_ux}',
        )
except Exception as e:
    record('K-AI Hybrid Engine, Broker, UI, KRunner & OCR Contract', 'FAIL', str(e))

# 23. Creator & Dual-Boot Bridges + NTSYNC Contract
try:
    pkgs_cfg_c4 = yaml.safe_load(open('recipes/packages.yml', 'r', encoding='utf-8'))
    pkgs_c4 = pkgs_cfg_c4.get('install', {}).get('packages', [])
    has_bridge_pkgs = all(p in pkgs_c4 for p in ['distrobox', 'freerdp', 'qemu-kvm', 'edk2-ovmf', 'efibootmgr', 'ffmpeg'])

    recipe_cfg_c4 = yaml.safe_load(open('recipes/recipe.yml', 'r', encoding='utf-8'))
    sys_en_c4 = next((m for m in recipe_cfg_c4.get('modules', []) if m.get('type') == 'systemd'), {}).get('system', {}).get('enabled', [])
    ntsync_mod = open('files/system/etc/modules-load.d/90-kushagra-ntsync.conf', 'r', encoding='utf-8').read()
    ntsync_udev = open('files/system/etc/udev/rules.d/90-kushagra-ntsync.rules', 'r', encoding='utf-8').read()
    has_ntsync_and_unit = (
        'kushagra-dualboot-detect.service' in sys_en_c4
        and 'k-ai-engine.service' not in sys_en_c4
        and 'ntsync' in ntsync_mod
        and 'KERNEL=="ntsync"' in ntsync_udev
        and 'MODE="0666"' in ntsync_udev
        and 'TAG+="uaccess"' in ntsync_udev
    )

    resolve_setup = open('files/system/usr/libexec/kushagra-resolve-setup', 'r', encoding='utf-8').read()
    resolve_conv = open('files/system/usr/bin/kushagra-resolve-convert', 'r', encoding='utf-8').read()
    resolve_kio = open('files/system/usr/share/kio/servicemenus/kushagra-resolve-convert.desktop', 'r', encoding='utf-8').read()
    winapps_setup = open('files/system/usr/libexec/kushagra-winapps-setup', 'r', encoding='utf-8').read()
    reboot_win = open('files/system/usr/bin/kushagra-reboot-windows', 'r', encoding='utf-8').read()
    reboot_desk = open('files/system/usr/share/applications/kushagra-reboot-windows.desktop', 'r', encoding='utf-8').read()
    dualboot_svc = open('files/system/usr/lib/systemd/system/kushagra-dualboot-detect.service', 'r', encoding='utf-8').read()
    just_v4_3 = open('files/system/usr/share/ublue-os/just/60-custom.just', 'r', encoding='utf-8').read()
    has_bridges = (
        'ghcr.io/zelikos/davincibox:latest' in resolve_setup
        and 'dnxhr_hq' in resolve_conv
        and 'kushagra-resolve-convert' in resolve_kio
        and 'MIN_RAM_KB=' in winapps_setup
        and 'MIN_DISK_GB=' in winapps_setup
        and 'efibootmgr --bootnext' in reboot_win
        and 'TryExec=/run/kushagra-windows-boot-available' in reboot_desk
        and '/run/kushagra-windows-boot-available' in dualboot_svc
        and all(r in just_v4_3 for r in ['install-resolve', 'setup-winapps', 'reboot-windows', 'k-ai-status'])
    )

    if has_bridge_pkgs and has_ntsync_and_unit and has_bridges:
        record(
            'Creator & Dual-Boot Bridges + NTSYNC Contract',
            'PASS',
            'DaVinci Resolve/DNxHR, KVM/FreeRDP3 WinApps, BootNext Dual-Boot detector & uaccess NTSYNC verified',
        )
    else:
        record(
            'Creator & Dual-Boot Bridges + NTSYNC Contract',
            'FAIL',
            f'has_bridge_pkgs={has_bridge_pkgs}, has_ntsync_and_unit={has_ntsync_and_unit}, has_bridges={has_bridges}',
        )
except Exception as e:
    record('Creator & Dual-Boot Bridges + NTSYNC Contract', 'FAIL', str(e))

# 24. Greenboot-rs Self-Healing Rollback Contract
try:
    pkgs_gb = yaml.safe_load(open('recipes/packages.yml', 'r', encoding='utf-8')).get('install', {}).get('packages', [])
    rec_gb = yaml.safe_load(open('recipes/recipe.yml', 'r', encoding='utf-8')).get('modules', [])
    s_idx_gb = next((i for i, m in enumerate(rec_gb) if m.get('type') == 'script'), -1)
    i_idx_gb = next((i for i, m in enumerate(rec_gb) if m.get('type') == 'initramfs'), -1)
    s_list_gb = rec_gb[s_idx_gb].get('scripts', []) if s_idx_gb >= 0 else []

    gb_conf = open('files/system/etc/greenboot/greenboot.conf', 'r', encoding='utf-8').read()
    gb_dropin = open('files/system/usr/lib/systemd/system/greenboot-set-rollback-trigger.service.d/10-kushagra-shutdown.conf', 'r', encoding='utf-8').read()
    gb_core = open('files/system/usr/lib/greenboot/check/required.d/10_kushagra_core.sh', 'r', encoding='utf-8').read()
    gb_gfx = open('files/system/usr/lib/greenboot/check/required.d/20_kushagra_graphics.sh', 'r', encoding='utf-8').read()
    gb_patch = open('files/scripts/06-patch-greenboot.sh', 'r', encoding='utf-8').read()

    net_leak = any(
        re.search(r'\b(curl|wget|ping|nc|ncat|nslookup)\b', txt)
        for txt in (gb_core, gb_gfx)
    )
    has_gb = (
        'greenboot' in pkgs_gb
        and 'greenboot-default-health-checks' not in pkgs_gb
        and 0 <= s_idx_gb < i_idx_gb
        and '06-patch-greenboot.sh' in s_list_gb
        and 'GREENBOOT_MAX_BOOT_ATTEMPTS=2' in gb_conf
        and 'Conflicts=final.target' in gb_dropin
        and 'Before=final.target' in gb_dropin
        and 'rd.live.image' in gb_core
        and 'rd.live.image' in gb_gfx
        and 'plasmalogin.service' in gb_gfx
        and '08_greenboot.cfg' in gb_patch
        and not net_leak
        and os.path.exists('files/system/usr/lib/greenboot/check/wanted.d/10_kushagra_desktop_sanity.sh')
        and os.path.exists('files/system/usr/lib/greenboot/red.d/10_kushagra_failure_log.sh')
        and os.path.exists('files/system/usr/lib/greenboot/green.d/10_kushagra_boot_ok.sh')
    )
    if has_gb:
        record('Greenboot-rs Self-Healing Rollback Contract', 'PASS', 'Offline desktop-safe greenboot-rs, MAX_BOOT_ATTEMPTS=2, #218 workarounds & zero net checks verified')
    else:
        record('Greenboot-rs Self-Healing Rollback Contract', 'FAIL', f'net_leak={net_leak}')
except Exception as e:
    record('Greenboot-rs Self-Healing Rollback Contract', 'FAIL', str(e))

# 25. Kushagra-DX (-dx), Verified Flathub Bazaar & LVFS fwupd Contract
try:
    dx_rec = yaml.safe_load(open('recipes/recipe-dx.yml', 'r', encoding='utf-8'))
    dx_pkgs = yaml.safe_load(open('recipes/dx-packages.yml', 'r', encoding='utf-8'))
    bz_cfg = yaml.safe_load(open('files/system/usr/share/kushagra-os/bazaar/config.yaml', 'r', encoding='utf-8'))
    bz_blk = yaml.safe_load(open('files/system/usr/share/kushagra-os/bazaar/blocklist.yaml', 'r', encoding='utf-8'))

    dx_raw = open('recipes/recipe-dx.yml', 'r', encoding='utf-8').read()
    dx_pkg_list = dx_pkgs.get('install', {}).get('packages', [])
    dx_mods = dx_rec.get('modules', [])
    has_brew_mod = any(m.get('type') == 'brew' and m.get('brew-analytics') is False for m in dx_mods)
    preset_dx = open('files/system/usr/lib/systemd/user-preset/85-kushagra-dx.preset', 'r', encoding='utf-8').read()
    fb_init = open('files/system/usr/libexec/kushagra-flatpak-verified-init', 'r', encoding='utf-8').read()
    fw_notify = open('files/system/usr/libexec/kushagra-fwupd-notify', 'r', encoding='utf-8').read()
    tuning_v5 = open('files/scripts/02-system-tuning.sh', 'r', encoding='utf-8').read()
    just_v5 = open('files/system/usr/share/ublue-os/just/60-custom.just', 'r', encoding='utf-8').read()
    rec_v5 = yaml.safe_load(open('recipes/recipe.yml', 'r', encoding='utf-8'))
    sys_en_v5 = next((m for m in rec_v5.get('modules', []) if m.get('type') == 'systemd'), {}).get('system', {}).get('enabled', [])

    blk_items = [b for grp in bz_blk.get('blocklists', []) for b in grp.get('block', [])]
    has_dx = (
        dx_rec.get('name') == 'kushagra-os-dx'
        and 'code' in dx_pkg_list
        and 'podman' in dx_pkg_list
        and 'type: rpm-ostree' not in dx_raw
        and has_brew_mod
        and 'systemctl disable docker.socket' in dx_raw
        and 'enable podman.socket' in preset_dx
        and 'enable kushagra-fwupd-notify.timer' in preset_dx
        and 'flathub-verified' in fb_init
        and '--subset=verified' in fb_init
        and 'com.visualstudio.code' in blk_items
        and '/run/host/etc/bazaar/blocklist.yaml' in bz_cfg.get('yaml-blocklist-paths', [])
        and 'org.kde.discover.notifier.desktop' in tuning_v5
        and 'Hidden=true' in tuning_v5
        and 'timeout 20 fwupdmgr get-updates --json' in fw_notify
        and 'BitLocker' in fw_notify
        and 'kushagra-flatpak-verified-init.service' in sys_en_v5
        and all(r in just_v5 for r in ['devmode:', 'dx-group:', 'flathub-unfilter:'])
    )
    if has_dx:
        record('Kushagra-DX, Verified Bazaar & LVFS fwupd Contract', 'PASS', 'recipe-dx, native code/brew/podman.socket, flathub-verified Bazaar & DiscoverNotifier->fwupd verified')
    else:
        record('Kushagra-DX, Verified Bazaar & LVFS fwupd Contract', 'FAIL', 'DX, Bazaar, or fwupd contract incomplete')
except Exception as e:
    record('Kushagra-DX, Verified Bazaar & LVFS fwupd Contract', 'FAIL', str(e))

# 26. Signed NVIDIA & Honest Linux EAC v2 Contract
try:
    import tomllib as _tomllib

    nv_rec = yaml.safe_load(open('recipes/recipe-nvidia.yml', 'r', encoding='utf-8'))
    dx_nv_rec = yaml.safe_load(open('recipes/recipe-dx-nvidia.yml', 'r', encoding='utf-8'))
    nv_kargs = _tomllib.loads(open('files/system/usr/lib/bootc/kargs.d/10-kushagra-nvidia.toml', 'r', encoding='utf-8').read())

    def _nv_order_ok(rec_obj):
        mods = rec_obj.get('modules', [])
        ak_idx = next((i for i, m in enumerate(mods) if m.get('type') == 'akmods'), -1)
        sig_idx = next((i for i, m in enumerate(mods) if m.get('type') == 'signing'), -1)
        ini_idx = next((i for i, m in enumerate(mods) if m.get('type') == 'initramfs'), -1)
        ak_mod = mods[ak_idx] if ak_idx >= 0 else {}
        return (
            ak_idx >= 0 and sig_idx > ak_idx and ini_idx > sig_idx
            and ak_mod.get('nvidia-driver') == 'nvidia-open'
        )

    mok_sh = open('files/system/usr/bin/kushagra-mok-enroll', 'r', encoding='utf-8').read()
    eac_stat = open('files/system/usr/bin/kushagra-eac-status', 'r', encoding='utf-8').read()
    eac_mode = open('files/system/usr/bin/kushagra-eac-mode', 'r', encoding='utf-8').read()
    tuning_nv = open('files/scripts/02-system-tuning.sh', 'r', encoding='utf-8').read()
    just_nv = open('files/system/usr/share/ublue-os/just/60-custom.just', 'r', encoding='utf-8').read()

    has_nv_eac = (
        nv_rec.get('name') == 'kushagra-os-nvidia'
        and dx_nv_rec.get('name') == 'kushagra-os-dx-nvidia'
        and _nv_order_ok(nv_rec)
        and _nv_order_ok(dx_nv_rec)
        and 'rd.driver.blacklist=nouveau' in nv_kargs.get('kargs', [])
        and 'nvidia-drm.modeset=1' in nv_kargs.get('kargs', [])
        and 'rm -f /usr/lib/bootc/kargs.d/10-kushagra-nvidia.toml' in tuning_nv
        and '12345678' in mok_sh
        and 'PCR 7' in mok_sh
        and 'rd.live.image' in mok_sh
        and 'selinux' in eac_stat and 'bpf' in eac_stat
        and 'lockdown=integrity' in eac_mode
        and 'iommu.passthrough=0' in eac_mode
        and 'kernel.kexec_load_disabled = 1' in eac_mode
        and 'Riot Vanguard' in eac_stat
        and all(r in just_nv for r in ['enroll-secure-boot-key', 'eac-status', 'eac-mode'])
    )
    if has_nv_eac:
        record('Signed NVIDIA & Honest Linux EAC v2 Contract', 'PASS', 'Signed nvidia-open recipes, non-NVIDIA karg isolation, MOK PCR 7 helper & EAC v2 tooling verified')
    else:
        record('Signed NVIDIA & Honest Linux EAC v2 Contract', 'FAIL', 'NVIDIA or EAC v2 contract check failed')
except Exception as e:
    record('Signed NVIDIA & Honest Linux EAC v2 Contract', 'FAIL', str(e))

# 27. Zero-Egress CI Chunking, Titanoboa Seekable OCI & Rule #13/#14 Contract
try:
    import tomllib as _tomllib_ci

    build_wf = yaml.safe_load(open('.github/workflows/build.yml', 'r', encoding='utf-8'))
    iso_wf = yaml.safe_load(open('.github/workflows/iso.yml', 'r', encoding='utf-8'))
    build_raw = open('.github/workflows/build.yml', 'r', encoding='utf-8').read()
    iso_raw = open('.github/workflows/iso.yml', 'r', encoding='utf-8').read()
    r2_conf = _tomllib_ci.loads(open('files/system/etc/containers/registries.conf.d/50-kushagra-mirror.conf', 'r', encoding='utf-8').read())
    r2_raw = open('files/system/etc/containers/registries.conf.d/50-kushagra-mirror.conf', 'r', encoding='utf-8').read()
    r2_sync = open('files/scripts/r2-sync-oci.sh', 'r', encoding='utf-8').read()
    arch_rules = open('.agents/rules/kushagra-architecture.md', 'r', encoding='utf-8').read()
    hc_raw = open('files/system/usr/bin/kushagra-health-check', 'r', encoding='utf-8').read()

    jobs = build_wf.get('jobs', {})
    derived_pr_safe = all(
        "github.event_name != 'pull_request'" in str(jobs.get(j, {}).get('if', ''))
        for j in ['bluebuild-dx', 'bluebuild-nvidia', 'bluebuild-dx-nvidia']
    )
    r2_regs = r2_conf.get('registry', [])
    no_wildcard_r2 = not any(r.get('location') == '*' for r in r2_regs) and 'location = "*"' not in r2_raw
    scoped_r2 = any('ghcr.io' in str(r.get('location', '')) for r in r2_regs)

    has_ci_oci = (
        "chunkah: 'true'" in build_raw
        and build_raw.count("max_layers: '92'") == 4
        and "squash: 'false'" in build_raw
        and "build_chunked_oci: 'false'" in build_raw
        and 'rechunk:' not in build_raw
        and '-gt 96' in build_raw
        and 'cosign verify --key cosign.pub' in build_raw
        and derived_pr_safe
        and '/run/initramfs/live/kushagra-oci' in iso_raw
        and '/work/iso-root/kushagra-oci' in iso_raw
        and 'skopeo copy' in iso_raw
        and 'OCI' in iso_raw
        and no_wildcard_r2
        and scoped_r2
        and 'R2_ACCOUNT_ID' in r2_sync
        and '[SKIP]' in r2_sync
        and '8 GB RAM Official 2026 Baseline' in arch_rules
        and 'Max-Parallel Fan-Out' in arch_rules
        and 'LOW_RAM_THRESHOLD_KB=3670016' in hc_raw
    )
    if has_ci_oci:
        record('Zero-Egress CI, Titanoboa OCI & Rules #13/#14 Contract', 'PASS', 'chunkah<=96 layers, cosign, seekable OCI dir, scoped R2 mirror & Rules #13/#14 verified')
    else:
        record('Zero-Egress CI, Titanoboa OCI & Rules #13/#14 Contract', 'FAIL', f'derived_pr_safe={derived_pr_safe}, no_wildcard_r2={no_wildcard_r2}, scoped_r2={scoped_r2}')
except Exception as e:
    record('Zero-Egress CI, Titanoboa OCI & Rules #13/#14 Contract', 'FAIL', str(e))

sys.exit(0 if all(r['status'] == 'PASS' for r in results) else 1)
