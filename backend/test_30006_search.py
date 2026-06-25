import requests

tests = ['shower hose', '30006', 'extendible', '3000630007', '30006-30007']
for q in tests:
    r = requests.get(f'http://localhost:8000/search-suggestions?q={q}')
    data = r.json()
    found = [s['text'] for s in data.get('suggestions',[]) if '30006' in s.get('text','')]
    label = found[:3] if found else 'NONE'
    print(f'Query [{q}]: {label}')
