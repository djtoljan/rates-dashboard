"""Fetch rates: CBR (RUB/unit) + XE (USD/unit) + Investing.com (RUB/unit), write to rates.json"""
import json, os, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

RATES_FILE = os.path.join(os.getcwd(), 'rates.json')

# Load existing data
try:
    with open(RATES_FILE) as f:
        data = json.load(f)
except:
    data = {}

# ─── CBR — RUB per unit ──────────────────────────────────
try:
    url = "https://www.cbr.ru/scripts/XML_daily.asp"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        xml_text = resp.read().decode('windows-1251')
    root = ET.fromstring(xml_text)
    targets = {'USD': 'R01235', 'EUR': 'R01239', 'CNY': 'R01375', 'TRY': 'R01700J'}
    cbr = {}
    for v in root.findall('Valute'):
        vid = v.get('ID')
        for code, tid in targets.items():
            if vid == tid:
                nominal = int(v.find('Nominal').text)
                value = float(v.find('Value').text.replace(',', '.'))
                cbr[code] = round(value / nominal, 4)
    data['cbr'] = cbr
    print('CBR:', cbr)
except Exception as e:
    print(f'CBR error: {e}')

# ─── XE — USD per unit (via open.er-api.com) ────────────
try:
    url = 'https://open.er-api.com/v6/latest/USD'
    req = urllib.request.Request(url, headers={'User-Agent': 'rates-dashboard/1.0'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        d = json.loads(resp.read())
    # API gives rates per 1 USD. We need USD per 1 unit = 1 / rate
    pairs = {'EUR': 'EUR', 'CNY': 'CNY', 'TRY': 'TRY'}
    xe = {}
    for code, key in pairs.items():
        if key in d['rates'] and d['rates'][key] > 0:
            xe[code] = round(1.0 / d['rates'][key], 4)
    data['xe'] = xe
    print('XE (USD/unit):', xe)
except Exception as e:
    print(f'XE error: {e}')

# ─── Investing.com — прямые RUB-пары (рыночные) ────────
try:
    import requests
    from bs4 import BeautifulSoup

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    # Прямые RUB-пары с investing.com — сразу RUB за единицу
    pairs = {
        'USD': 'https://www.investing.com/currencies/usd-rub',
        'EUR': 'https://www.investing.com/currencies/eur-rub',
        'CNY': 'https://www.investing.com/currencies/cny-rub',
        'TRY': 'https://www.investing.com/currencies/try-rub',
    }

    investing = {}
    for code, url in pairs.items():
        try:
            r = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(r.text, 'html.parser')
            el = soup.find('div', {'data-test': 'instrument-price-last'})
            if el:
                investing[code] = float(el.text.strip().replace(',', ''))
                print(f'  {code}/RUB: {investing[code]}')
            else:
                print(f'  {code}/RUB: element not found')
        except Exception as e:
            print(f'  {code}/RUB: {e}')

    if investing:
        data['investing'] = investing
        print('Investing.com (RUB/unit):', investing)

except Exception as e:
    print(f'Investing.com error: {e}')

# ─── Save ─────────────────────────────────────────────────
data['updated'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
with open(RATES_FILE, 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(f'Saved to {RATES_FILE}')
