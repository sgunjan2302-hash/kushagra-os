#!/usr/bin/env python3
import os
import sys
import time
import socket
import subprocess
import shutil
from PIL import Image

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
raw_iso = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else os.path.join(REPO_ROOT, "build", "v0.1.6", "KushagraOS-44.iso")
VERBOSE_GRUB = "--verbose" in sys.argv
ISO_PATH = os.path.abspath(raw_iso)
BUILD_DIR = os.path.dirname(ISO_PATH)
QEMU_DIR = os.path.join(REPO_ROOT, "build", "qemu")
QEMU_BIN = os.path.join(QEMU_DIR, "qemu-system-x86_64.exe")
SERIAL_LOG = os.path.join(BUILD_DIR, "serial.log")
QEMU_PPM = os.path.join(QEMU_DIR, "screen.ppm")
ARTIFACT_DIR = r"C:\Users\sgunj\.gemini\antigravity\brain\282037fa-b7e1-44d0-be26-2adfcb5e1f34"

print(f"=== Kushagra OS LiveCD VM Boot Test (enforcing=0) ===")
print(f"ISO: {ISO_PATH} ({os.path.getsize(ISO_PATH):,} bytes)")
print(f"QEMU: {QEMU_BIN}")

if os.path.exists(SERIAL_LOG):
    try:
        os.remove(SERIAL_LOG)
    except Exception:
        pass
if os.path.exists(QEMU_PPM):
    try:
        os.remove(QEMU_PPM)
    except Exception:
        pass

# Paths for QEMU arguments
iso_arg = ISO_PATH.replace("\\", "/")
serial_arg = f"file:{SERIAL_LOG.replace(chr(92), '/')}"

cmd = [
    QEMU_BIN,
    "-L", "share",
    "-M", "q35",
    "-accel", "tcg,thread=multi",
    "-m", "4096",
    "-smp", "4",
    "-drive", "if=pflash,format=raw,readonly=on,file=share/edk2-x86_64-code.fd",
    "-cdrom", iso_arg,
    "-boot", "d",
    "-vga", "std",
    "-serial", serial_arg,
    "-monitor", "tcp:127.0.0.1:4444,server,nowait",
    "-display", "none"
]

print(f"Starting QEMU process...")
proc = subprocess.Popen(
    cmd,
    cwd=QEMU_DIR,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

time.sleep(2)
if proc.poll() is not None:
    stdout, stderr = proc.communicate()
    print(f"[FAIL] QEMU terminated immediately! Code: {proc.returncode}")
    print(f"STDERR: {stderr}")
    sys.exit(1)

print(f"QEMU running with PID: {proc.pid}")

# Connect to QEMU monitor promptly (before 1s hidden GRUB expires when --verbose is used)
s = None
for attempt in range(25):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.5)
        s.connect(("127.0.0.1", 4444))
        time.sleep(0.15)
        greeting = s.recv(4096).decode('utf-8', errors='ignore')
        print(f"Connected to QEMU Monitor:\n{greeting.strip()}")
        break
    except Exception:
        s = None
        time.sleep(0.2)

if not s:
    print("[WARN] Could not connect to QEMU monitor socket")

def send_monitor(cmd_str):
    if not s: return
    try:
        s.sendall(f"{cmd_str}\r\n".encode('utf-8'))
        time.sleep(0.1)
        try:
            s.recv(1024)
        except Exception:
            pass
    except Exception as e:
        print(f"[WARN monitor error] {e}")

start_time = time.time()
last_serial_pos = 0
last_snap_time = 0
snapshots_saved = []
verbose_selected = False

try:
    while time.time() - start_time < 150:
        elapsed = int(time.time() - start_time)
        if VERBOSE_GRUB and not verbose_selected:
            serial_so_far = ""
            if os.path.exists(SERIAL_LOG):
                try:
                    serial_so_far = open(SERIAL_LOG, "r", encoding="utf-8", errors="ignore").read()
                except Exception:
                    pass
            if "BdsDxe: starting" in serial_so_far or "GRUB" in serial_so_far or elapsed >= 1:
                verbose_selected = True
                send_monitor("sendkey esc")
                time.sleep(0.25)
                send_monitor("sendkey down")
                time.sleep(0.2)
                send_monitor("sendkey ret")

        # Check if QEMU died
        if proc.poll() is not None:
            stdout, stderr = proc.communicate()
            print(f"\n[ALERT] QEMU exited at {elapsed}s with code: {proc.returncode}")
            print(f"STDERR: {stderr}")
            break

        # Read serial log
        if os.path.exists(SERIAL_LOG):
            try:
                with open(SERIAL_LOG, "r", encoding="utf-8", errors="ignore") as f:
                    f.seek(last_serial_pos)
                    new_text = f.read()
                    last_serial_pos = f.tell()
                    if new_text:
                        for line in new_text.splitlines():
                            clean = line.strip()
                            if clean:
                                print(f"[{elapsed:02d}s SERIAL] {clean}", flush=True)
            except Exception:
                pass

        # Capture screenshot every 10 seconds or at key checkpoints
        if s and (elapsed - last_snap_time >= 10 or elapsed in (5, 12, 25, 45, 60, 90)):
            last_snap_time = elapsed
            if os.path.exists(QEMU_PPM):
                try:
                    os.remove(QEMU_PPM)
                except Exception:
                    pass

            send_monitor("screendump screen.ppm")
            time.sleep(0.3)

            if os.path.exists(QEMU_PPM) and os.path.getsize(QEMU_PPM) > 0:
                png_name = f"boot_{elapsed:02d}s.png"
                png_dest = os.path.join(BUILD_DIR, png_name)
                try:
                    with Image.open(QEMU_PPM) as img:
                        img.save(png_dest, format="PNG")
                    print(f"[{elapsed:02d}s SCREEN] Saved {png_name} ({os.path.getsize(png_dest):,} bytes)", flush=True)
                    if os.path.isdir(ARTIFACT_DIR):
                        shutil.copy2(png_dest, os.path.join(ARTIFACT_DIR, png_name))
                    snapshots_saved.append(png_dest)
                except Exception as ex:
                    print(f"[{elapsed:02d}s SCREEN ERROR] {ex}", flush=True)

        time.sleep(2)

finally:
    print("\nTerminating VM...")
    if s:
        try:
            s.close()
        except Exception:
            pass
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    print("VM terminated.")
    print(f"Total screenshots captured: {len(snapshots_saved)}")
