import urllib.request
import subprocess
import os
import sys
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
art_id = '14900819271'
url = f'https://api.github.com/repos/sgunjan2302-hash/kushagra-os/actions/artifacts/{art_id}/zip'

out_dir = r'F:\KUSHAGRA OS\build\v0.1.8'
os.makedirs(out_dir, exist_ok=True)
zip_path = os.path.join(out_dir, 'KushagraOS-44-iso.zip')

print(f"Fetching redirect URL for artifact {art_id}...")
opener = urllib.request.build_opener(NoAuthRedirect)
req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}', 'User-Agent': 'Mozilla/5.0'})

with opener.open(req) as resp:
    total_size = int(resp.headers.get('Content-Length', 0))
    print(f"Downloading {total_size} bytes to {zip_path}...")
    downloaded = 0
    with open(zip_path, 'wb') as f:
        while chunk := resp.read(1024 * 1024 * 4): # 4MB chunks
            f.write(chunk)
            downloaded += len(chunk)
            pct = (downloaded / total_size * 100) if total_size else 0
            if downloaded % (1024 * 1024 * 100) < (1024 * 1024 * 4):
                print(f"Downloaded {downloaded // (1024*1024)} MB ({pct:.1f}%)")

print("Download complete. Extracting ISO...")
with zipfile.ZipFile(zip_path, 'r') as zf:
    zf.extractall(out_dir)

print("Extracted files in:", out_dir)
for f in os.listdir(out_dir):
    p = os.path.join(out_dir, f)
    print(f"  {f} ({os.path.getsize(p)} bytes)")
