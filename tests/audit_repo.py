import glob
import os
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

# Verify via git that no private keys are tracked or staged
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

# 6. Line Endings Check
all_sh = glob.glob('files/scripts/*.sh') + ['files/system/usr/bin/kushagra-layout-switch', 'files/system/usr/bin/kushagra-health-check']
crlf_files = []
for s in all_sh:
    raw = open(s, 'rb').read()
    if b'\r' in raw:
        crlf_files.append(s)
if not crlf_files:
    record('LF Line Endings', 'PASS', f'All {len(all_sh)} scripts/executables have clean Unix LF')
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

sys.exit(0 if all(r['status'] == 'PASS' for r in results) else 1)

