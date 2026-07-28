/**
 * fetch-rates.js — Comprehensive rate fetcher for dashboard
 * Sources: CBR (XML), Investing.com (curl + JSON-LD), XFeepay (API)
 * Pushes to GitHub Pages via API (no git required)
 */

const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// ─── CONFIG ─────────────────────────────────────────────
const TOKEN = 'ghp_pIv5OrB1aF0nPBG0aXg2GsSmH3F6Gq3VFldR';
const OWNER = 'djtoljan';
const REPO = 'rates-dashboard';
const FILE = 'rates.json';

const RATES_PATH = path.join(__dirname, 'rates.json');
const CURL_PATH = 'C:\\Windows\\System32\\curl.exe';

const CURRENCIES = ['USD', 'EUR', 'CNY', 'TRY'];

function log(msg) {
  const ts = new Date().toLocaleString('ru-RU', { timeZone: 'Europe/Moscow' });
  console.log(`[${ts}] ${msg}`);
}

// ─── HELPERS ────────────────────────────────────────────
function curlGet(url, timeout = 15) {
  try {
    const stdout = execSync(
      `"${CURL_PATH}" -s -L --max-time ${timeout} ` +
      `-H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" ` +
      `-H "Accept: text/html,application/xhtml+xml" ` +
      `-H "Accept-Language: ru-RU,ru;q=0.9" ` +
      `"${url}"`,
      { timeout: (timeout + 5) * 1000, encoding: 'utf8', maxBuffer: 5 * 1024 * 1024 }
    );
    return stdout || '';
  } catch (e) {
    log(`  curl error for ${url}: ${e.message.slice(0, 100)}`);
    return '';
  }
}

function parseJsonLd(html) {
  const match = html.match(/<script[^>]*type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/);
  if (!match) return {};
  try {
    const data = JSON.parse(match[1]);
    if (data['@type'] !== 'FAQPage') return {};
    const qa = {};
    for (const item of data.mainEntity || []) {
      qa[item.name || ''] = (item.acceptedAnswer || {}).text || '';
    }
    return qa;
  } catch (e) {
    return {};
  }
}

function parseRateFromQA(qa, keyPrefix = 'Exchange Rate') {
  for (const [q, a] of Object.entries(qa)) {
    if (q.includes(keyPrefix)) {
      const nums = a.match(/[\d]+\.[\d]+/);
      if (nums) return parseFloat(nums[0]);
    }
  }
  return null;
}

function httpsGetJson(url, timeout = 15) {
  return new Promise((resolve, reject) => {
    const proto = url.startsWith('https') ? https : http;
    const req = proto.get(url, { timeout: timeout * 1000, headers: { 'User-Agent': 'Mozilla/5.0' } }, res => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch (e) { reject(new Error(`JSON parse: ${e.message}`)); }
      });
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
  });
}

// ─── GITHUB API ─────────────────────────────────────────
function githubApi(method, urlPath, body) {
  return new Promise((resolve, reject) => {
    const bodyStr = body ? JSON.stringify(body) : undefined;
    const opts = {
      hostname: 'api.github.com',
      path: urlPath,
      method,
      headers: {
        'Authorization': 'Bearer ' + TOKEN,
        'User-Agent': 'openclaw-rates-updater/2.0',
        'Content-Type': 'application/json',
      }
    };
    if (bodyStr) opts.headers['Content-Length'] = Buffer.byteLength(bodyStr);

    const req = https.request(opts, res => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => {
        try { resolve({ status: res.statusCode, body: JSON.parse(data) }); }
        catch (e) { resolve({ status: res.statusCode, body: data }); }
      });
    });
    req.on('error', reject);
    req.setTimeout(30000, () => { req.destroy(); reject(new Error('timeout')); });
    if (bodyStr) req.write(bodyStr);
    req.end();
  });
}

async function pushToGithub(rates) {
  const filePath = '/repos/' + OWNER + '/' + REPO + '/contents/' + FILE;

  // Get current SHA
  const getResp = await githubApi('GET', filePath);
  if (getResp.status !== 200) {
    log('❌ GitHub GET failed: ' + getResp.status + ' ' + JSON.stringify(getResp.body).slice(0, 200));
    return false;
  }

  const sha = getResp.body.sha;
  const contentB64 = Buffer.from(JSON.stringify(rates, null, 2)).toString('base64');
  const ts = new Date(rates.updated).toISOString().replace('T', ' ').slice(0, 16);

  const putResp = await githubApi('PUT', filePath, {
    message: '🔄 rates update ' + ts + ' MSK',
    content: contentB64,
    sha: sha,
    branch: 'main'
  });

  if (putResp.status === 201 || putResp.status === 200) {
    log('✅ Pushed to GitHub! SHA: ' + (putResp.body.content?.sha || 'ok'));
    return true;
  } else {
    log('❌ Push failed: ' + putResp.status + ' ' + JSON.stringify(putResp.body).slice(0, 300));
    return false;
  }
}

// ─── FETCHERS ───────────────────────────────────────────
async function fetchCBR() {
  log('Fetching CBR...');
  try {
    const xml = await new Promise((resolve, reject) => {
      https.get('https://www.cbr.ru/scripts/XML_daily.asp', {
        headers: { 'User-Agent': 'Mozilla/5.0' },
        timeout: 15000
      }, res => {
        const chunks = [];
        res.on('data', c => chunks.push(c));
        res.on('end', () => resolve(Buffer.concat(chunks)));
      }).on('error', reject);
    });

    // Simple XML parsing without external deps
    const xmlStr = require('iconv-lite').decode(xml, 'win1251');
    const targets = { 'USD': 'R01235', 'EUR': 'R01239', 'CNY': 'R01375', 'TRY': 'R01700J' };
    const cbr = {};

    const valuteRegex = /<Valute ID="([^"]+)">([\s\S]*?)<\/Valute>/g;
    let match;
    while ((match = valuteRegex.exec(xmlStr)) !== null) {
      const id = match[1];
      const inner = match[2];
      for (const [code, tid] of Object.entries(targets)) {
        if (id === tid) {
          const nominalMatch = inner.match(/<Nominal>(\d+)<\/Nominal>/);
          const valueMatch = inner.match(/<Value>([\d,]+)<\/Value>/);
          if (nominalMatch && valueMatch) {
            const nominal = parseInt(nominalMatch[1]);
            const value = parseFloat(valueMatch[1].replace(',', '.'));
            cbr[code] = Math.round((value / nominal) * 1e4) / 1e4;
          }
        }
      }
    }
    log('CBR: ' + JSON.stringify(cbr));
    return cbr;
  } catch (e) {
    log('❌ CBR error: ' + e.message);
    return null;
  }
}

async function fetchInvesting() {
  log('Fetching Investing.com RUB rates...');
  const rubPairs = {
    'USD': 'https://www.investing.com/currencies/usd-rub',
    'EUR': 'https://www.investing.com/currencies/eur-rub',
    'CNY': 'https://www.investing.com/currencies/cny-rub',
    'TRY': 'https://www.investing.com/currencies/try-rub',
  };
  const investing = {};

  for (const [code, url] of Object.entries(rubPairs)) {
    const html = curlGet(url);
    if (!html) { log(`  ${code}: empty response`); continue; }
    const qa = parseJsonLd(html);
    const rate = parseRateFromQA(qa);
    if (rate) {
      investing[code] = Math.round(rate * 1e4) / 1e4;
      log(`  ${code}/RUB: ${investing[code]}`);
    } else {
      log(`  ${code}/RUB: rate not found`);
    }
  }

  if (Object.keys(investing).length > 0) {
    log('Investing (RUB/unit): ' + JSON.stringify(investing));
    return investing;
  }
  log('❌ Investing: all pairs failed');
  return null;
}

async function fetchCrossRates() {
  log('Fetching cross-rates (Investing.com)...');
  const crossPairs = {
    'EUR': 'https://www.investing.com/currencies/eur-usd',
    'CNY': 'https://www.investing.com/currencies/usd-cny',
    'TRY': 'https://www.investing.com/currencies/usd-try',
  };
  const xe = {};

  for (const [code, url] of Object.entries(crossPairs)) {
    const html = curlGet(url);
    if (!html) { log(`  ${code}: empty response`); continue; }
    const qa = parseJsonLd(html);
    const rate = parseRateFromQA(qa);
    if (rate && rate > 0) {
      if (code === 'EUR') {
        xe[code] = Math.round(rate * 1e4) / 1e4;
      } else {
        xe[code] = Math.round((1.0 / rate) * 1e4) / 1e4;
      }
      log(`  ${code}/USD: ${xe[code]}`);
    } else {
      log(`  ${code}: rate not found`);
    }
  }

  if (Object.keys(xe).length > 0) {
    log('Cross-rates (USD/unit): ' + JSON.stringify(xe));
    return xe;
  }

  // Fallback to open.er-api.com
  log('Falling back to open.er-api.com...');
  try {
    const data = await httpsGetJson('https://open.er-api.com/v6/latest/USD');
    const rates = data.rates || {};
    const fb = {};
    if (rates['EUR']) fb['EUR'] = Math.round(rates['EUR'] * 1e8) / 1e8;
    if (rates['CNY']) fb['CNY'] = Math.round((1.0 / rates['CNY']) * 1e8) / 1e8;
    if (rates['TRY']) fb['TRY'] = Math.round((1.0 / rates['TRY']) * 1e8) / 1e8;
    if (Object.keys(fb).length > 0) {
      log('Fallback cross-rates: ' + JSON.stringify(fb));
      return fb;
    }
  } catch (e) {
    log('Fallback error: ' + e.message);
  }
  return null;
}

async function fetchXFeepay() {
  log('Fetching XFeepay...');
  const xfee = {};
  for (const code of ['CNH', 'EUR']) {
    try {
      const url = `https://xfeepay.com/e-core/api/exchange/channelRate?sourceCurrency=USD&targetCurrency=${code}`;
      const data = await httpsGetJson(url);
      const rt = data?.data?.realTimeRate;
      if (rt && rt > 0) {
        xfee[code] = Math.round(rt * 1e4) / 1e4;
        log(`  XFee ${code}: ${xfee[code]}`);
      }
    } catch (e) {
      log(`  XFee ${code}: ${e.message}`);
    }
  }
  if (Object.keys(xfee).length > 0) {
    log('XFeepay: ' + JSON.stringify(xfee));
    return xfee;
  }
  log('❌ XFeepay: all failed');
  return null;
}

// ─── MAIN ───────────────────────────────────────────────
async function main() {
  log('=== Starting rates update ===');

  // Load existing
  let data = {};
  if (fs.existsSync(RATES_PATH)) {
    try { data = JSON.parse(fs.readFileSync(RATES_PATH, 'utf8')); }
    catch (e) { data = {}; }
  }

  // Fetch all sources in parallel
  const [cbr, investing, xe, xfee] = await Promise.all([
    fetchCBR(),
    fetchInvesting(),
    fetchCrossRates(),
    fetchXFeepay(),
  ]);

  // Merge results (preserve existing if fetch failed)
  if (cbr) data.cbr = cbr;
  if (investing) data.investing = investing;
  if (xe) data.xe = xe;
  if (xfee) data.xfee = xfee;

  data.updated = new Date().toISOString();

  // Write locally
  fs.writeFileSync(RATES_PATH, JSON.stringify(data, null, 2));
  log('Saved locally: ' + RATES_PATH);

  // Push to GitHub
  const pushed = await pushToGithub(data);
  log(pushed ? '=== Done (pushed) ===' : '=== Done (local only) ===');
  return pushed;
}

main().catch(e => {
  log('❌ FATAL: ' + e.message);
  process.exit(1);
});
