import subprocess
import time
import os
import sys

def main():
    print("[1/5] Setting up VM environment in WSL2...")
    setup_cmd = """
mkdir -p /tmp/kushagra_test
mkdir -p "/mnt/f/KUSHAGRA OS/build/screenshots"
rm -f /tmp/kushagra_test/monitor.sock /tmp/kushagra_test/serial.log /tmp/kushagra_test/screen.ppm
cp -f /usr/share/OVMF/OVMF_VARS_4M.fd /tmp/kushagra_test/ovmf_vars.fd
"""
    subprocess.run(["wsl", "-d", "Ubuntu-24.04", "-u", "root", "--", "bash", "-c", setup_cmd], check=True)

    print("[2/5] Creating runner script in WSL2...")
    wsl_script = """#!/usr/bin/env python3
import subprocess
import socket
import time
import os
import sys
from PIL import Image

iso_path = '/mnt/f/KUSHAGRA OS/build/KushagraOS-44.iso'
artifact_dir = '/mnt/c/Users/sgunj/.gemini/antigravity/brain/282037fa-b7e1-44d0-be26-2adfcb5e1f34'
screenshots_dir = '/mnt/f/KUSHAGRA OS/build/screenshots'
sock_path = '/tmp/kushagra_test/monitor.sock'
ppm_path = '/tmp/kushagra_test/screen.ppm'
serial_path = '/tmp/kushagra_test/serial.log'

qemu_cmd = [
    'qemu-system-x86_64',
    '-enable-kvm',
    '-cpu', 'host',
    '-m', '4096',
    '-smp', '2',
    '-drive', 'if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd',
    '-drive', 'if=pflash,format=raw,file=/tmp/kushagra_test/ovmf_vars.fd',
    '-cdrom', iso_path,
    '-boot', 'd',
    '-vga', 'std',
    '-chardev', 'socket,id=mon0,path=/tmp/kushagra_test/monitor.sock,server=on,wait=off',
    '-mon', 'chardev=mon0,mode=readline',
    '-serial', f'file:{serial_path}',
    '-display', 'none'
]

print("Launching QEMU process...")
proc = subprocess.Popen(qemu_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# Wait for monitor socket
for _ in range(30):
    if os.path.exists(sock_path):
        break
    time.sleep(0.5)

if not os.path.exists(sock_path):
    print("ERROR: QEMU monitor socket did not appear!")
    proc.kill()
    sys.exit(1)

print("QEMU monitor socket connected. Monitoring boot...")

def send_mon_cmd(cmd):
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(sock_path)
        time.sleep(0.1)
        s.recv(4096)
        s.sendall(cmd.encode() + b'\\n')
        time.sleep(0.2)
        resp = s.recv(4096)
        s.close()
        return resp.decode(errors='replace')
    except Exception as e:
        return f"ERR: {e}"

def capture_screen(name):
    if os.path.exists(ppm_path):
        os.remove(ppm_path)
    send_mon_cmd(f"screendump {ppm_path}")
    time.sleep(0.4)
    if os.path.exists(ppm_path) and os.path.getsize(ppm_path) > 0:
        try:
            img = Image.open(ppm_path)
            png_local = os.path.join(screenshots_dir, f"{name}.png")
            png_artifact = os.path.join(artifact_dir, f"{name}.png")
            img.save(png_local)
            img.save(png_artifact)
            colors = img.getcolors(maxcolors=256)
            num_c = len(colors) if colors else ">256"
            print(f"[{name}] {img.size[0]}x{img.size[1]} ({num_c} colors) -> saved {name}.png")
            return True
        except Exception as e:
            print(f"[{name}] Image conversion failed: {e}")
            return False
    else:
        print(f"[{name}] PPM not found or empty")
        return False

# Monitor loop over 90 seconds
start_time = time.time()
sent_enter = False
step = 0

while time.sleep(5) or (time.time() - start_time < 90):
    elapsed = int(time.time() - start_time)
    step += 1
    tag = f"boot_{elapsed:02d}s"
    capture_screen(tag)

    if elapsed >= 10 and not sent_enter:
        print(f"[{elapsed}s] Sending ENTER key to select default GRUB entry...")
        send_mon_cmd("sendkey ret")
        sent_enter = True

    if proc.poll() is not None:
        print(f"QEMU exited prematurely with code {proc.returncode} at {elapsed}s")
        break

print("[Serial log snippet]")
if os.path.exists(serial_path):
    with open(serial_path, 'r', errors='replace') as sf:
        serial_content = sf.read()
        print(serial_content[-2000:] if serial_content else "(empty serial log)")
else:
    print("No serial log file.")

print("Terminating QEMU...")
proc.terminate()
try:
    proc.wait(timeout=5)
except subprocess.TimeoutExpired:
    proc.kill()

print("Boot test finished cleanly.")
"""
    with open("tests/wsl_runner.py", "w", newline="\n") as f:
        f.write(wsl_script)

    print("[3/5] Starting boot test in WSL2...")
    res = subprocess.run(["wsl", "-d", "Ubuntu-24.04", "-u", "root", "--", "python3", "/mnt/f/KUSHAGRA OS/tests/wsl_runner.py"])
    print(f"Runner completed with exit code {res.returncode}")

if __name__ == "__main__":
    main()
