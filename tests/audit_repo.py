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
    'DNSOverTLS=yes': 'files/system/etc/systemd/resolved.conf.d/10-dot-opportunistic.conf'
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
    + glob.glob('files/system/usr/libexec/kushagra-*')
    + glob.glob('files/system/usr/share/kushagra-os/oobe/*.py')
    + glob.glob('files/system/usr/share/kushagra-os/oobe/*.qml')
    + glob.glob('files/system/usr/share/kushagra-os/installer/*.py')
    + glob.glob('files/system/usr/share/kushagra-os/installer/*.qml')
    + glob.glob('files/system/usr/share/kushagra-os/winrun/*.py')
    + [
        'files/system/usr/share/kushagra-os/livesys/livesys-session-extra',
        'files/system/usr/lib/systemd/system/kushagra-oobe.service',
        'files/system/usr/lib/tmpfiles.d/kushagra-oobe.conf',
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

# 8. Validate Titanoboa iso.yaml Contract
try:
    with open('files/system/usr/lib/bootc-image-builder/iso.yaml', 'r', encoding='utf-8') as fp:
        iso_cfg = yaml.safe_load(fp)
    entries = iso_cfg.get('grub2', {}).get('entries', [])
    valid_entries = all('name' in e and 'linux' in e and 'initrd' in e for e in entries)
    has_enforcing = all('enforcing=0' in e.get('linux', '') for e in entries)
    if iso_cfg.get('label') and entries and valid_entries and has_enforcing:
        record('Titanoboa iso.yaml Contract', 'PASS', f'Valid label "{iso_cfg.get("label")}" with {len(entries)} GRUB2 entries (enforcing=0 verified)')
    else:
        record('Titanoboa iso.yaml Contract', 'FAIL', f'Invalid iso.yaml entries structure or missing enforcing=0: {entries}')
except Exception as e:
    record('Titanoboa iso.yaml Contract', 'FAIL', str(e))

# 9. LiveCD Initramfs Dracut Modules Contract
try:
    with open('recipes/packages.yml', 'r', encoding='utf-8') as f:
        pkgs_cfg = yaml.safe_load(f)
    install_pkgs = pkgs_cfg.get('install', {}).get('packages', [])
    has_dracut_live = 'dracut-live' in install_pkgs

    has_live_conf = os.path.exists('files/system/etc/dracut.conf.d/livecd.conf')
    conf_valid = False
    if has_live_conf:
        with open('files/system/etc/dracut.conf.d/livecd.conf', 'r', encoding='utf-8') as f:
            conf_text = f.read()
            conf_valid = 'dmsquash-live' in conf_text

    if has_dracut_live and conf_valid:
        record('LiveCD Dracut Modules', 'PASS', 'dracut-live in packages.yml and dmsquash-live in livecd.conf')
    else:
        record('LiveCD Dracut Modules', 'FAIL', f'has_dracut_live={has_dracut_live}, conf_valid={conf_valid}')
except Exception as e:
    record('LiveCD Dracut Modules', 'FAIL', str(e))

# 10. UEFI LiveCD Bootloader Hardening Contract
try:
    with open('.github/workflows/iso.yml', 'r', encoding='utf-8') as f:
        iso_workflow = f.read()
    has_grub_boot_stage = '/out/EFI/BOOT/grubx64.efi' in iso_workflow
    has_fb_purge = 'fbx64.efi' in iso_workflow and 'rm -vf' in iso_workflow
    has_tpm_unload = 'rmmod tpm' in iso_workflow

    if has_grub_boot_stage and has_fb_purge and has_tpm_unload:
        record('UEFI Bootloader Resilience', 'PASS', 'grubx64.efi staged in EFI/BOOT, fbx64.efi purged, and rmmod tpm injected')
    else:
        record('UEFI Bootloader Resilience', 'FAIL', f'has_grub_boot_stage={has_grub_boot_stage}, has_fb_purge={has_fb_purge}, has_tpm_unload={has_tpm_unload}')
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
        and 'kushagra-oobe-handoff' in oobe_apply_txt
        and 'systemctl stop plasmalogin.service' in oobe_apply_txt
        and 'systemctl start plasmalogin.service' in oobe_apply_txt
        and 'qdbus-qt6' in layout_sh_txt
        and '(`wheel`)' not in qml_text
        and 'focusPolicy: Qt.NoFocus' in qml_text
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

# 15. Stage 1 Custom Qt6/QML K-Installer Contract (v0.2.0 + v0.2.1 bootc/ESP/GPT fixes)
try:
    required_installer_files = [
        'files/system/usr/bin/kushagra-installer',
        'files/system/usr/libexec/kushagra-installer-autostart',
        'files/system/usr/libexec/kushagra-installer-backend',
        'files/system/etc/xdg/autostart/kushagra-installer-autostart.desktop',
        'files/system/usr/share/applications/kushagra-installer.desktop',
        'files/system/etc/anaconda/profile.d/kushagra-os.conf',
        'files/system/etc/polkit-1/rules.d/50-kushagra-installer.rules',
        'files/system/usr/share/polkit-1/actions/org.kushagraos.installer.policy',
        'files/system/usr/share/kushagra-os/installer/main.py',
        'files/system/usr/share/kushagra-os/installer/Main.qml',
        'files/system/usr/share/kushagra-os/installer/storage_probe.py',
        'files/system/usr/share/kushagra-os/installer/ks_builder.py',
        'files/system/usr/share/kushagra-os/installer/anaconda_runner.py',
    ]
    missing_inst = [p for p in required_installer_files if not os.path.exists(p)]

    for py_path in [
        'files/system/usr/share/kushagra-os/installer/main.py',
        'files/system/usr/share/kushagra-os/installer/storage_probe.py',
        'files/system/usr/share/kushagra-os/installer/ks_builder.py',
        'files/system/usr/share/kushagra-os/installer/anaconda_runner.py',
        'files/system/usr/libexec/kushagra-installer-backend',
    ]:
        if os.path.exists(py_path):
            ast.parse(open(py_path, 'r', encoding='utf-8').read(), filename=py_path)

    if os.path.exists('files/system/usr/share/polkit-1/actions/org.kushagraos.installer.policy'):
        ET.parse('files/system/usr/share/polkit-1/actions/org.kushagraos.installer.policy')

    autostart_sh = open('files/system/usr/libexec/kushagra-installer-autostart', 'r', encoding='utf-8').read()
    profile_txt = open('files/system/etc/anaconda/profile.d/kushagra-os.conf', 'r', encoding='utf-8').read()
    probe_txt = open('files/system/usr/share/kushagra-os/installer/storage_probe.py', 'r', encoding='utf-8').read()
    ks_txt = open('files/system/usr/share/kushagra-os/installer/ks_builder.py', 'r', encoding='utf-8').read()
    backend_txt = open('files/system/usr/libexec/kushagra-installer-backend', 'r', encoding='utf-8').read()
    runner_txt = open('files/system/usr/share/kushagra-os/installer/anaconda_runner.py', 'r', encoding='utf-8').read()
    inst_qml = open('files/system/usr/share/kushagra-os/installer/Main.qml', 'r', encoding='utf-8').read()
    livesys_extra = open('files/system/usr/share/kushagra-os/livesys/livesys-session-extra', 'r', encoding='utf-8').read()

    has_live_gate = 'rd.live.image' in autostart_sh and 'liveuser' in autostart_sh
    has_profile = 'os_id = kushagra-os' in profile_txt and 'base_profile = fedora-kinoite' in profile_txt
    has_safety_locks = (
        'WIN_FSTYPES' in probe_txt
        and 'ESP_PARTTYPES' in probe_txt
        and 'MIN_ESP_FREE_MIB = 35' in probe_txt
        and 'detect_live_disk_paths' in probe_txt
        and 'os.path.basename' in probe_txt
        and 'needsInitGpt' in probe_txt
    )
    has_ks_handoff = (
        'clearpart --none' in ks_txt
        and 'rootpw --lock' in ks_txt
        and 'firstboot --disable' in ks_txt
        and '/var/lib/kushagra-oobe-pending' in ks_txt
        and 'bootloader --location=none' in ks_txt
        and '/var/home' in ks_txt
        and 'grub2-editenv' in ks_txt
        and 'efibootmgr' in ks_txt
        and '/boot/efi/EFI/fedora/grub.cfg' in ks_txt
        and '/boot/efi/EFI/BOOT/grub.cfg' in ks_txt
        and 'in (eng)' in ks_txt
        and 'graphical.target' in ks_txt
        and 'setfiles' in ks_txt
        and 'vmlinuz' in ks_txt
        and not re.search(r'^\s*user\s+', ks_txt, re.MULTILINE)
    )
    has_anaconda_cmd = (
        '--liveinst' not in backend_txt
        and '--cmdline' in backend_txt
        and '--kickstart' in backend_txt
        and 'DBUS_SESSION_BUS_ADDRESS' in backend_txt
        and 'anaconda_runner.py' in backend_txt
        and 'security.capability' in backend_txt
        and 'can_reboot' in runner_txt
        and 'can_activate_keyboard' in runner_txt
    )
    has_qml_screens = all(k in inst_qml for k in ['Install Kushagra OS', 'Try Live Desktop', 'installLogsText', 'espLowSpace'])
    has_livesys_kiosk = (
        'kushagra-installer.desktop' in livesys_extra
        and 'org.kde.plasma-welcome.desktop' in livesys_extra
        and 'chown -R liveuser:liveuser /home/liveuser' in livesys_extra
        and 'plasma-welcomerc' in livesys_extra
        and 'drkonqi' in livesys_extra
        and 'kscreenlockerrc' in livesys_extra
        and 'plasma-powerdevil.service' in livesys_extra
    )

    if not missing_inst and has_live_gate and has_profile and has_safety_locks and has_ks_handoff and has_anaconda_cmd and has_qml_screens and has_livesys_kiosk:
        record(
            'Kushagra K-Installer Stage 1 Contract',
            'PASS',
            'LiveCD kiosk gate, storage/Windows/EFI locks, Anaconda cmdline Kickstart backend, bootc GRUB2/EFI staging & OOBE handoff verified',
        )
    else:
        record(
            'Kushagra K-Installer Stage 1 Contract',
            'FAIL',
            f'missing={missing_inst}, has_live_gate={has_live_gate}, has_profile={has_profile}, '
            f'has_safety_locks={has_safety_locks}, has_ks_handoff={has_ks_handoff}, '
            f'has_anaconda_cmd={has_anaconda_cmd}, has_qml_screens={has_qml_screens}, has_livesys_kiosk={has_livesys_kiosk}',
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
    has_v021_branding = (
        'v0.2.1' in recipe_raw
        and 'v0.1 Prototype' not in recipe_raw
        and 'v0.2.1' in issue_raw
        and 'v0.1 Prototype' not in issue_raw
    )

    if has_live_guards and has_app_fixes and has_v021_branding:
        record(
            'v0.2.1 LiveCD Guards & Branding Contract',
            'PASS',
            'LiveCD flatpak/bootloader guards, Bottles/system gaming fixes, and v0.2.1 branding verified',
        )
    else:
        record(
            'v0.2.1 LiveCD Guards & Branding Contract',
            'FAIL',
            f'has_live_guards={has_live_guards}, has_app_fixes={has_app_fixes}, has_v021_branding={has_v021_branding}',
        )
except Exception as e:
    record('v0.2.1 LiveCD Guards & Branding Contract', 'FAIL', str(e))

sys.exit(0 if all(r['status'] == 'PASS' for r in results) else 1)
