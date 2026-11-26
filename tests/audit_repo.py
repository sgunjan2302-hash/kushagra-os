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

# 6. Line Endings Check (scripts, OOBE Python/QML, systemd unit)
lf_targets = (
    glob.glob('files/scripts/*.sh')
    + glob.glob('files/system/usr/bin/kushagra-*')
    + glob.glob('files/system/usr/libexec/kushagra-*')
    + glob.glob('files/system/usr/share/kushagra-os/oobe/*.py')
    + glob.glob('files/system/usr/share/kushagra-os/oobe/*.qml')
    + ['files/system/usr/lib/systemd/system/kushagra-oobe.service']
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

# 12. Graphical Dual-Boot Installer & WebUI Browser Contract (v0.1.9)
try:
    pkgs_cfg = yaml.safe_load(open('recipes/packages.yml', 'r', encoding='utf-8'))
    install_pkgs = pkgs_cfg.get('install', {}).get('packages', [])
    remove_pkgs = pkgs_cfg.get('remove', {}).get('packages', [])
    desktop_launcher = 'files/system/etc/skel/Desktop/liveinst.desktop'
    just_file = 'files/system/usr/share/ublue-os/just/60-custom.just'

    has_anaconda = 'anaconda-live' in install_pkgs and 'partitionmanager' in install_pkgs
    has_firefox_webui = 'firefox' in install_pkgs and 'firefox' not in remove_pkgs
    has_launcher = os.path.exists(desktop_launcher) and 'Exec=liveinst' in open(desktop_launcher, encoding='utf-8').read()
    has_just_recipe = 'install-to-disk' in open(just_file, encoding='utf-8').read()

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
    has_tmpfiles_var = (
        'f /var/lib/kushagra-oobe-pending 0644 root root - -' in tmpfiles_text
        and 'C /var/lib/livesys/livesys-session-extra' in tmpfiles_text
    )
    has_uid_guard = '$3 >= 1000' in bootutil_text and '/var/lib/kushagra-oobe-pending' in tuning_text
    has_all_screens = all(k in qml_text for k in ['en_IN', 'hi_IN', 'nmcli', 'Familiar Mode', 'Studio Mode', 'autoLoginSwitch', 'oobeBackend.finishSetup'])

    if not missing_oobe and has_oobe_pkg and has_systemd_cfg and has_unit_guards and has_tmpfiles_var and has_uid_guard and has_all_screens:
        record(
            'Kushagra Setup OOBE Contract',
            'PASS',
            'Qt6/QML OOBE wizard, tmpfiles.d /var persistence, systemd bootutil guards, scoped Polkit helper, and recipe systemd settings verified',
        )
    else:
        record(
            'Kushagra Setup OOBE Contract',
            'FAIL',
            f'missing={missing_oobe}, has_oobe_pkg={has_oobe_pkg}, has_systemd_cfg={has_systemd_cfg}, '
            f'has_unit_guards={has_unit_guards}, has_tmpfiles_var={has_tmpfiles_var}, has_uid_guard={has_uid_guard}, has_all_screens={has_all_screens}',
        )
except Exception as e:
    record('Kushagra Setup OOBE Contract', 'FAIL', str(e))

sys.exit(0 if all(r['status'] == 'PASS' for r in results) else 1)
