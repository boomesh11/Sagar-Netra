import urllib.request, json, time
from pathlib import Path

time.sleep(5)
boundary = '----TestBoundary123'
img_bytes = Path('tests/fixtures/wreck_real.png').read_bytes()
body = (
    f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="wreck_real.png"\r\nContent-Type: image/png\r\n\r\n'.encode()
    + img_bytes
    + f'\r\n--{boundary}--\r\n'.encode()
)
req = urllib.request.Request(
    'http://localhost:8000/api/upload',
    data=body,
    headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
    method='POST'
)
try:
    resp = urllib.request.urlopen(req, timeout=60)
    data = json.loads(resp.read())
    print('STATUS:', data.get('status'))
    print('MODE:  ', data.get('mode'))
    targets = data.get('targets', [])
    print('TARGETS:', len(targets))
    if targets:
        t = targets[0]
        pos = t.get('position', {})
        print('FIRST TARGET:', t['id'], '->', t['decision'], t['confidence'])
        print('POSITION STATUS:', pos.get('position_status'))
except Exception as e:
    print('ERROR:', e)
