import urllib.request
import json
import subprocess

def get_token():
    p = subprocess.Popen(['git', 'credential', 'fill'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    out, _ = p.communicate('protocol=https\nhost=github.com\npath=sgunjan2302-hash/kushagra-os.git\n\n')
    creds = dict(line.split('=', 1) for line in out.strip().splitlines() if '=' in line)
    return creds.get('password')

token = get_token()

class NoAuthRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_req and 'Authorization' in new_req.headers:
            del new_req.headers['Authorization']
        return new_req

opener = urllib.request.build_opener(NoAuthRedirect)

headers = {'User-Agent': 'Mozilla/5.0'}
if token:
    headers['Authorization'] = f'Bearer {token}'

runs_url = 'https://api.github.com/repos/sgunjan2302-hash/kushagra-os/actions/runs'
req = urllib.request.Request(runs_url, headers=headers)
runs = json.loads(opener.open(req).read()).get('workflow_runs', [])
iso_runs = [r for r in runs if r.get('name') == 'Build Bootable LiveCD ISO']
latest = iso_runs[0]
print(f"=== Fetching logs for Run #{latest.get('run_number')} ({latest.get('id')}) ===")

jreq = urllib.request.Request(latest.get('jobs_url'), headers=headers)
jobs = json.loads(opener.open(jreq).read()).get('jobs', [])
job_id = jobs[0]['id']

log_url = f"https://api.github.com/repos/sgunjan2302-hash/kushagra-os/actions/jobs/{job_id}/logs"
lreq = urllib.request.Request(log_url, headers=headers)
raw_logs = opener.open(lreq).read().decode('utf-8', errors='replace')
print("=== LOG OUTPUT (Last 4000 characters) ===")
print(raw_logs[-4000:])
