import urllib.request
import subprocess
import os
import sys
import json
import time
import zipfile

def get_token():
    p = subprocess.Popen(['git', 'credential', 'fill'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    out, _ = p.communicate('protocol=https\nhost=github.com\npath=sgunjan2302-hash/kushagra-os.git\n\n')
    creds = dict(line.split('=', 1) for line in out.strip().splitlines() if '=' in line)
    return creds.get('password')

class NoAuthRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if 'Authorization' in new_req.headers:
            del new_req.headers['Authorization']
        return new_req

token = get_token()
headers = {'Authorization': f'Bearer {token}', 'User-Agent': 'Mozilla/5.0'}

run_id = '45356909131'
print(f"Tracking ISO Run #{run_id}...")

while True:
    url = f'https://api.github.com/repos/sgunjan2302-hash/kushagra-os/actions/runs/{run_id}'
    req = urllib.request.Request(url, headers=headers)
    try:
        data = json.loads(urllib.request.urlopen(req).read().decode())
        status = data.get('status')
        conclusion = data.get('conclusion')
        print(f"[{time.strftime('%H:%M:%S')}] Status: {status}, Conclusion: {conclusion}")
        if status == 'completed':
            if conclusion != 'success':
                print(f"Run failed with conclusion: {conclusion}")
                sys.exit(1)
            break
    except Exception as e:
        print("Polling error:", e)
    time.sleep(20)

# Fetch artifact
art_url = f'https://api.github.com/repos/sgunjan2302-hash/kushagra-os/actions/runs/{run_id}/artifacts'
req = urllib.request.Request(art_url, headers=headers)
artifacts = json.loads(urllib.request.urlopen(req).read().decode()).get('artifacts', [])
iso_art = next((a for a in artifacts if a['name'] == 'KushagraOS-44-iso'), None)
if not iso_art:
    print("Error: No KushagraOS-44-iso artifact found!")
    sys.exit(1)

art_id = iso_art['id']
print(f"Found artifact ID: {art_id} ({iso_art['size_in_bytes']} bytes)")

out_dir = r'F:\KUSHAGRA OS\build\v0.1.8'
os.makedirs(out_dir, exist_ok=True)
zip_path = os.path.join(out_dir, 'KushagraOS-44-iso.zip')

download_url = f'https://api.github.com/repos/sgunjan2302-hash/kushagra-os/actions/artifacts/{art_id}/zip'
opener = urllib.request.build_opener(NoAuthRedirect)
req = urllib.request.Request(download_url, headers=headers)

with opener.open(req) as resp:
    total_size = int(resp.headers.get('Content-Length', 0))
    print(f"Downloading {total_size} bytes to {zip_path}...")
    downloaded = 0
    with open(zip_path, 'wb') as f:
        while chunk := resp.read(1024 * 1024 * 8):
            f.write(chunk)
            downloaded += len(chunk)
            pct = (downloaded / total_size * 100) if total_size else 0
            if downloaded % (1024 * 1024 * 200) < (1024 * 1024 * 8):
                print(f"Downloaded {downloaded // (1024*1024)} MB ({pct:.1f}%)")

print("Download complete. Extracting ISO...")
with zipfile.ZipFile(zip_path, 'r') as zf:
    zf.extractall(out_dir)

print("Files in out_dir:")
for f in os.listdir(out_dir):
    p = os.path.join(out_dir, f)
    print(f"  {f} ({os.path.getsize(p)} bytes)")
