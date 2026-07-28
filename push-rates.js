/**
 * push-rates.js — пушит rates.json в GitHub через API
 * Токен вшит, git не требуется.
 */
const https = require('https');
const fs = require('fs');
const path = require('path');

const TOKEN = process.env.GH_TOKEN || '';
if (!TOKEN) { console.log('❌ GH_TOKEN env var not set'); process.exit(1); }
const OWNER = 'djtoljan';
const REPO = 'rates-dashboard';
const FILE = 'rates.json';

const filePath = path.join(__dirname, FILE);
if (!fs.existsSync(filePath)) {
    console.log('❌ rates.json не найден:', filePath);
    process.exit(1);
}

const content = fs.readFileSync(filePath, 'utf8');
const contentB64 = Buffer.from(content).toString('base64');

function apiRequest(method, urlPath, body) {
    return new Promise((resolve, reject) => {
        const opts = {
            hostname: 'api.github.com',
            path: urlPath,
            method: method,
            headers: {
                'Authorization': 'token ' + TOKEN,
                'User-Agent': 'openclaw-rates-updater',
                'Content-Type': 'application/json',
            }
        };
        if (body) {
            opts.headers['Content-Length'] = Buffer.byteLength(body);
        }
        const req = https.request(opts, res => {
            let data = '';
            res.on('data', c => data += c);
            res.on('end', () => {
                try { resolve({ status: res.statusCode, body: JSON.parse(data) }); }
                catch(e) { resolve({ status: res.statusCode, body: data }); }
            });
        });
        req.on('error', reject);
        if (body) req.write(body);
        req.end();
    });
}

(async () => {
    try {
        // Get current SHA
        const getPath = '/repos/' + OWNER + '/' + REPO + '/contents/' + FILE;
        const getResp = await apiRequest('GET', getPath);
        if (getResp.status !== 200) {
            console.log('❌ GET failed:', getResp.status, JSON.stringify(getResp.body).slice(0, 200));
            process.exit(1);
        }
        const sha = getResp.body.sha;

        // Read updated rates
        const rates = JSON.parse(content);
        const ts = new Date(rates.updated).toISOString().replace('T',' ').slice(0,16);
        
        // Push
        const putBody = JSON.stringify({
            message: '🔄 rates update ' + ts + ' MSK',
            content: contentB64,
            sha: sha,
            branch: 'main'
        });

        const putResp = await apiRequest('PUT', getPath, putBody);
        if (putResp.status === 201 || putResp.status === 200) {
            console.log('✅ Pushed! New SHA:', putResp.body.content?.sha);
            console.log('   Updated:', ts, 'MSK');
        } else {
            console.log('❌ Push failed:', putResp.status, JSON.stringify(putResp.body).slice(0, 300));
            process.exit(1);
        }
    } catch(e) {
        console.log('❌ Error:', e.message);
        process.exit(1);
    }
})();
