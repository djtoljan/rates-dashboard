"""Fetch rates: CBR (RUB/unit) + XE (USD/unit), write to rates.json"""
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

# ─── Yahoo Finance — market rates → all to RUB ──────────
try:
    import yfinance as yf
    raw = {}
    # Fetch market quotes: USD/RUB, EUR/USD, USD/CNY, USD/TRY
    tickers = {'USDRUB': 'USDRUB=X', 'EURUSD': 'EURUSD=X', 'USDCNY': 'USDCNY=X', 'USDTRY': 'USDTRY=X'}
    for key, ticker in tickers.items():
        t = yf.Ticker(ticker)
        d = t.history(period='1d')
        if not d.empty:
            raw[key] = round(float(d['Close'].iloc[-1]), 4)
        else:
            info = t.info
            price = info.get('regularMarketPrice') or info.get('previousClose')
            if price:
                raw[key] = round(float(price), 4)
    # Convert all to RUB per unit
    yahoo = {}
    usd_rub = raw.get('USDRUB', 0)
    if usd_rub:
        yahoo['USD'] = usd_rub                          # USD/RUB
        if raw.get('EURUSD'):
            yahoo['EUR'] = round(raw['EURUSD'] * usd_rub, 4)   # EUR/RUB
        if raw.get('USDCNY'):
            yahoo['CNY'] = round(usd_rub / raw['USDCNY'], 4)   # CNY/RUB
        if raw.get('USDTRY'):
            yahoo['TRY'] = round(usd_rub / raw['USDTRY'], 4)   # TRY/RUB
    data['yahoo'] = yahoo
    print('Yahoo (RUB/unit):', yahoo)
except Exception as e:
    print(f'Yahoo error: {e}')

# ─── XFeepay — from xfee-rates.json (local scraper) ──────
try:
    xfee_file = os.path.join(os.getcwd(), 'xfee-rates.json')
    if os.path.exists(xfee_file):
        with open(xfee_file) as f:
            xd = json.load(f)
        xfee = {}
        usd_rub = data.get('cbr', {}).get('USD', 0)
        # USD/EUR: 1 USD = X EUR → EUR/USD = 1/X, EUR/RUB = usd_rub / X
        if xd.get('USD_EUR') and usd_rub:
            xfee['EUR'] = round(usd_rub / xd['USD_EUR'], 4)
        # USD/CNH: 1 USD = X CNH → CNH/RUB = usd_rub / X
        if xd.get('USD_CNH') and usd_rub:
            xfee['CNY'] = round(usd_rub / xd['USD_CNH'], 4)
        # XFeepay doesn't have USD/RUB or TRY directly, leave empty
        if xfee:
            data['xfee'] = xfee
            print('XFeepay (RUB/unit):', xfee)
except Exception as e:
    print(f'XFeepay error: {e}')

# ─── Save ─────────────────────────────────────────────────
data['updated'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
with open(RATES_FILE, 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(f'Saved to {RATES_FILE}')
