"""Fetch CBR + Frankfurter rates, write to rates.json"""
import json, os, sys, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# In GitHub Actions, cwd is the repo root — write rates.json there
RATES_FILE = os.path.join(os.getcwd(), 'rates.json')

# Load existing data
try:
    with open(RATES_FILE) as f:
        data = json.load(f)
except:
    data = {}

# ─── CBR ──────────────────────────────────────────────────
try:
    cbr_url = "https://www.cbr.ru/scripts/XML_daily.asp"
    req = urllib.request.Request(cbr_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        xml_text = resp.read().decode('windows-1251')
    root = ET.fromstring(xml_text)
    rates = {}
    targets = {'USD': 'R01235', 'EUR': 'R01239', 'CNY': 'R01375'}
    for v in root.findall('Valute'):
        vid = v.get('ID')
        for code, tid in targets.items():
            if vid == tid:
                nominal = int(v.find('Nominal').text)
                value = float(v.find('Value').text.replace(',', '.'))
                rates[code] = round(value / nominal, 4)
    data['cbr'] = rates
    print('CBR:', rates)
except Exception as e:
    print(f'CBR error: {e}')

# ─── Frankfurter (XE-like) ────────────────────────────────
try:
    rates = {}
    pairs = ['USD', 'EUR', 'CNY']
    for p in pairs:
        url = f'https://api.frankfurter.app/latest?from={p}&to=RUB'
        req = urllib.request.Request(url, headers={'User-Agent': 'rates-dashboard/1.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            d = json.loads(resp.read())
            rates[p] = round(d['rates']['RUB'], 4)
    data['xe'] = rates
    print('XE:', rates)
except Exception as e:
    print(f'XE error: {e}')

# ─── Save ─────────────────────────────────────────────────
data['updated'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
with open(RATES_FILE, 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(f'Saved to {RATES_FILE}')
