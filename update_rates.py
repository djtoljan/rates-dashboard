"""Fetch rates: CBR (RUB/unit) + open.er-api.com cross-rates + XFeepay, write to rates.json"""
import json, os, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

RATES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rates.json')

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

# ─── Cross-rates — open.er-api.com (USD per unit) ────────
try:
    import requests as req_xe
    xe = {}
    
    # EUR/USD
    try:
        r = req_xe.get('https://open.er-api.com/v6/latest/EUR', timeout=15)
        xe['EUR'] = float(r.json()['rates']['USD'])
        print(f'  EUR/USD: {xe["EUR"]}')
    except Exception as e:
        print(f'  EUR/USD error: {e}')
    
    # USD/CNY (invert to USD per 1 CNY) + USD/TRY (invert)
    try:
        r = req_xe.get('https://open.er-api.com/v6/latest/USD', timeout=15)
        rates = r.json()['rates']
        xe['CNY'] = 1.0 / float(rates['CNY'])
        xe['TRY'] = 1.0 / float(rates['TRY'])
        print(f'  CNY/USD: {xe["CNY"]}')
        print(f'  TRY/USD: {xe["TRY"]}')
    except Exception as e:
        print(f'  USD pairs error: {e}')
    
    if xe:
        data['xe'] = xe
        print('Cross-rates (USD/unit):', xe)
except Exception as e:
    print(f'Cross-rates error: {e}')

# ─── XFeepay — market rates ──────────────────────────────
try:
    import requests as req_xfee
    xfee = {}
    
    xfee_pairs = {'CNH': 'CNH', 'EUR': 'EUR'}
    for code, cur in xfee_pairs.items():
        try:
            url = f'https://xfeepay.com/e-core/api/exchange/channelRate?sourceCurrency=USD&targetCurrency={cur}'
            r = req_xfee.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            d = r.json()
            rt = d.get('data', {}).get('realTimeRate')
            if rt and rt > 0:
                xfee[code] = float(rt)
                print(f'  XFee {cur}: {xfee[code]} (1 USD = {xfee[code]} {cur})')
        except Exception as e:
            print(f'  XFee {cur}: {e}')
    
    if xfee:
        data['xfee'] = xfee
        print('XFeepay:', xfee)
except Exception as e:
    print(f'XFeepay error: {e}')

# ─── Save ─────────────────────────────────────────────────
data['updated'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
with open(RATES_FILE, 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(f'Saved to {RATES_FILE}')
