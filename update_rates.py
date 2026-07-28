"""
update_rates.py — Multi-source currency rate aggregator with 3-tier fallback
Tier 1: CBR (official daily) + MOEX ISS (real-time RUB pairs)
Tier 2: api.exchangerate.fun (hourly cross-rates) + XFeepay (real-time, Q8)
Tier 3: Cross-validation — flag anomalies >2% deviation
Writes rates.json for GitHub Pages dashboard
"""
import json, os, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

RATES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rates.json')

try:
    with open(RATES_FILE) as f:
        data = json.load(f)
except:
    data = {}

alerts = []

# ═══ TIER 1 — Official sources ═══

# CBR (Central Bank of Russia) — daily official RUB rates
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
    alerts.append('CBR: DOWN')

# MOEX ISS — real-time market RUB pairs
try:
    moex = {}
    pairs = {'USD/RUB': 'USD', 'EUR/RUB': 'EUR'}
    for pair, code in pairs.items():
        try:
            moex_url = f'https://iss.moex.com/iss/statistics/engines/futures/markets/indicativerates/securities/{pair.replace("/","/")}.json?iss.meta=off&iss.only=securities.current'
            req = urllib.request.Request(moex_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                d = json.loads(resp.read().decode())
            current = d.get('securities.current', {}).get('data', [])
            if current:
                moex[code] = {
                    'rate': float(current[0][3]),
                    'time': f"{current[0][1]} {current[0][2]}"
                }
                print(f'  MOEX {pair}: {moex[code]["rate"]} @ {moex[code]["time"]}')
        except Exception as e:
            print(f'  MOEX {pair}: {e}')
    if moex:
        data['moex'] = moex
except Exception as e:
    print(f'MOEX error: {e}')
    alerts.append('MOEX: DOWN')

# ═══ TIER 2 — Market cross-rates ═══

# api.exchangerate.fun — hourly, free, no key
try:
    import requests as req_erf
    r = req_erf.get('https://api.exchangerate.fun/latest?base=USD', timeout=15)
    rates = r.json().get('rates', {})
    cross = {}
    for code in ['EUR', 'CNY', 'TRY', 'RUB']:
        if code in rates and rates[code] > 0:
            cross[code] = float(rates[code])
    if cross:
        data['cross'] = cross
        data['cross_source'] = 'exchangerate.fun'
        print('Cross-rates (exchangerate.fun):', cross)
except Exception as e:
    print(f'Cross-rates error: {e}')
    alerts.append('exchangerate.fun: DOWN')

# XFeepay — real-time, Q8 trusted source
try:
    import requests as req_xfee
    xfee = {}
    for cur in ['CNH', 'EUR']:
        try:
            url = f'https://xfeepay.com/e-core/api/exchange/channelRate?sourceCurrency=USD&targetCurrency={cur}'
            r = req_xfee.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            rt = r.json().get('data', {}).get('realTimeRate')
            if rt and rt > 0:
                xfee[cur] = float(rt)
                print(f'  XFee {cur}: {xfee[cur]} (1 USD = {xfee[cur]} {cur})')
        except Exception as e:
            print(f'  XFee {cur}: {e}')
    if xfee:
        data['xfee'] = xfee
except Exception as e:
    print(f'XFeepay error: {e}')
    alerts.append('XFeepay: DOWN')

# ═══ TIER 3 — Cross-validation ═══

def validate(name, val1, val2, threshold=0.02):
    if val1 and val2 and val1 > 0 and val2 > 0:
        diff = abs(val1 - val2) / min(val1, val2)
        if diff > threshold:
            msg = f'{name}: {val1:.4f} vs {val2:.4f} (d{round(diff*100,1)}%)'
            alerts.append(msg)
            print(f'  !! {msg}')

# MOEX vs CBR
if 'moex' in data and 'cbr' in data:
    for code in ['USD', 'EUR']:
        moex_val = data['moex'].get(code, {}).get('rate')
        cbr_val = data['cbr'].get(code)
        if moex_val and cbr_val:
            validate(f'{code}/RUB MOEX vs CBR', moex_val, cbr_val, 0.03)

if alerts:
    data['alerts'] = alerts
elif 'alerts' in data:
    del data['alerts']

# Remove stale legacy keys
for old_key in ['investing', 'xe', 'open-er-api']:
    data.pop(old_key, None)

data['updated'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

with open(RATES_FILE, 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f'Saved. Sources: CBR={bool(data.get("cbr"))} MOEX={bool(data.get("moex"))} cross={bool(data.get("cross"))} XFee={bool(data.get("xfee"))}')
if alerts:
    print(f'!! Alerts ({len(alerts)}):')
    for a in alerts:
        print(f'   - {a}')
