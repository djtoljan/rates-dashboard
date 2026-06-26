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

# ─── Investing.com — все курсы (RUB-пары + кросс-курсы) ─
try:
    import requests
    from bs4 import BeautifulSoup

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    # Прямые RUB-пары — RUB за единицу
    rub_pairs = {
        'USD': 'https://www.investing.com/currencies/usd-rub',
        'EUR': 'https://www.investing.com/currencies/eur-rub',
        'CNY': 'https://www.investing.com/currencies/cny-rub',
        'TRY': 'https://www.investing.com/currencies/try-rub',
    }

    investing = {}
    for code, url in rub_pairs.items():
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

    # Кросс-курсы (USD за единицу) — вместо XE/open.er-api.com
    cross_pairs = {
        'EUR': 'https://www.investing.com/currencies/eur-usd',      # USD per 1 EUR
        'CNY': 'https://www.investing.com/currencies/usd-cny',      # CNY per 1 USD → invert
        'TRY': 'https://www.investing.com/currencies/usd-try',      # TRY per 1 USD → invert
    }

    xe = {}
    for code, url in cross_pairs.items():
        try:
            r = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(r.text, 'html.parser')
            el = soup.find('div', {'data-test': 'instrument-price-last'})
            if el:
                val = float(el.text.strip().replace(',', ''))
                if code == 'EUR':
                    xe[code] = val  # EUR/USD = USD per 1 EUR
                else:
                    xe[code] = round(1.0 / val, 4)  # invert: USD/CNY → CNY per 1 USD → USD per 1 CNY
                print(f'  {code}/USD: {xe[code]}')
            else:
                print(f'  {code}/USD: element not found')
        except Exception as e:
            print(f'  {code}/USD: {e}')

    if xe:
        data['xe'] = xe
        print('Investing.com cross (USD/unit):', xe)

except Exception as e:
    print(f'Investing.com error: {e}')

# ─── XFeepay — CNH + EUR (USD per unit, без авторизации) ─
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
                xfee[code] = round(rt, 4)
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
