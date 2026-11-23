import urllib.request
import json
import subprocess
import sys

def get_github_token():
    try:
        p = subprocess.Popen(['git', 'credential', 'fill'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        out, _ = p.communicate('protocol=https\nhost=github.com\npath=sgunjan2302-hash/kushagra-os.git\n\n')
        creds = dict(line.split('=', 1) for line in out.strip().splitlines() if '=' in line)
        return creds.get('password')
    except Exception:
        return None

token = get_github_token()
headers = {'User-Agent': 'Mozilla/5.0'}
if token:
    headers['Authorization'] = f'Bearer {token}'

try:
    runs_url = 'https://api.github.com/repos/sgunjan2302-hash/kushagra-os/actions/runs'
    req = urllib.request.Request(runs_url, headers=headers)
    runs = json.loads(urllib.request.urlopen(req).read()).get('workflow_runs', [])
    iso_runs = [r for r in runs if r.get('name') == 'Build Bootable LiveCD ISO']
    if not iso_runs:
        print("No ISO runs found")
        sys.exit(0)
    latest = iso_runs[0]
    print(f"=== ISO Run #{latest.get('run_number')} (Status: {latest.get('status')}, Conclusion: {latest.get('conclusion')}) ===")
    print(f"URL: {latest.get('html_url')}")
    jobs_url = latest.get('jobs_url')
    jreq = urllib.request.Request(jobs_url, headers=headers)
    jobs = json.loads(urllib.request.urlopen(jreq).read()).get('jobs', [])
    for job in jobs:
        print(f"\n--- Job: {job.get('name')} (Status: {job.get('status')}, Conclusion: {job.get('conclusion')}) ---")
        for s in job.get('steps', []):
            st = s.get('status')
            conc = s.get('conclusion')
            icon = '⏳' if st == 'in_progress' else ('✅' if conc == 'success' else ('❌' if conc == 'failure' else '⚪'))
            print(f"  {icon} {s.get('name')}: {st} ({conc})")
except Exception as e:
    print(f"Error polling: {e}")
