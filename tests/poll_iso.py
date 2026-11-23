import urllib.request
import json

try:
    url = 'https://api.github.com/repos/sgunjan2302-hash/kushagra-os/actions/runs/45172658924/jobs'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    res = json.loads(urllib.request.urlopen(req).read())
    for job in res.get('jobs', []):
        print(f"=== Job: {job.get('name')} (Status: {job.get('status')}, Conclusion: {job.get('conclusion')}) ===")
        print(f"Started: {job.get('started_at')}")
        for s in job.get('steps', []):
            st = s.get('status')
            conc = s.get('conclusion')
            icon = '⏳' if st == 'in_progress' else ('✅' if conc == 'success' else ('❌' if conc == 'failure' else '⚪'))
            print(f"  {icon} {s.get('name')}: {st} ({conc})")
except Exception as e:
    print(f"Error polling: {e}")
