// Netlify Function: report-bug
// Receives bug reports from web/game clients, validates, rate-limits, and
// forwards to GitHub via repository_dispatch so a workflow can create the issue.

// Env vars required in Netlify site settings:
// - GITHUB_DISPATCH_TOKEN: Fine-grained PAT or GitHub App installation token with permission to dispatch events
// - GITHUB_REPO: "owner/repo" (e.g., "PipFoweraker/pdoom1-website")
// Optional:
// - ALLOWED_ORIGIN: CORS allowlist for browser submissions
// - DRY_RUN: if set, skips the GitHub API call (useful for local tests)

const crypto = require('crypto');

const ok = (body, origin) => ({
  statusCode: 200,
  headers: corsHeaders(origin),
  body: JSON.stringify(body),
});

const bad = (status, message, origin) => ({
  statusCode: status,
  headers: corsHeaders(origin),
  body: JSON.stringify({ error: message }),
});

const corsHeaders = (origin) => {
  const allow = process.env.ALLOWED_ORIGIN || origin || '*';
  return {
    'Access-Control-Allow-Origin': allow,
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
  };
};

// very simple in-memory rate-limit (best effort; per-instance)
const rl = new Map();
function rateLimited(key, limitPerMin = 5) {
  const now = Date.now();
  const windowMs = 60_000;
  const start = now - windowMs;
  const arr = (rl.get(key) || []).filter((t) => t > start);
  if (arr.length >= limitPerMin) return true;
  arr.push(now);
  rl.set(key, arr);
  return false;
}

function sha256(s) {
  return crypto.createHash('sha256').update(String(s), 'utf8').digest('hex');
}

function sanitize(input) {
  const maxTitle = 120;
  const maxDesc = 10_000;
  const maxLogs = 20_000;
  const out = {};
  out.title = (input.title || '').toString().trim().slice(0, maxTitle);
  out.description = (input.description || '').toString().trim().slice(0, maxDesc);
  out.type = (input.type || 'bug').toString().toLowerCase();
  out.email = (input.email || '').toString().trim().slice(0, 320);
  out.source = (input.source || 'web').toString().toLowerCase();
  out.appVersion = (input.appVersion || '').toString().trim().slice(0, 64);
  out.buildId = (input.buildId || '').toString().trim().slice(0, 64);
  out.os = (input.os || '').toString().trim().slice(0, 128);
  out.logs = (input.logs || '').toString().slice(0, maxLogs);
  out.notify = Boolean(input.notify);
  // enforce allowed types
  const allowed = ['bug', 'feature', 'documentation', 'performance'];
  if (!allowed.includes(out.type)) out.type = 'bug';
  return out;
}

async function dispatchToGitHub(payload) {
  if (process.env.DRY_RUN) {
    return { ok: true, dryRun: true };
  }

  const token = process.env.GITHUB_DISPATCH_TOKEN;
  const repo = process.env.GITHUB_REPO;
  if (!token || !repo) {
    throw new Error('Server not configured: missing GITHUB_DISPATCH_TOKEN or GITHUB_REPO');
  }
  const [owner, name] = repo.split('/');
  const url = `https://api.github.com/repos/${owner}/${name}/dispatches`;

  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Authorization': `token ${token}`,
      'Accept': 'application/vnd.github+json',
      'Content-Type': 'application/json',
      'User-Agent': 'pdoom1-report-bug-fn',
    },
    body: JSON.stringify({
      event_type: 'bug-report',
      client_payload: payload,
    }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`GitHub dispatch failed: ${res.status} ${text}`);
  }
  return { ok: true };
}

exports.handler = async function handler(event) {
  const origin = event.headers?.origin || '*';

  if (event.httpMethod === 'OPTIONS') {
    return {
      statusCode: 204,
      headers: corsHeaders(origin),
    };
  }

  if (event.httpMethod !== 'POST') {
    return bad(405, 'Method Not Allowed', origin);
  }

  let body;
  try {
    body = JSON.parse(event.body || '{}');
  } catch (e) {
    return bad(400, 'Invalid JSON body', origin);
  }

  const ip = event.headers['x-forwarded-for']?.split(',')[0]?.trim() || event.ip || 'unknown';
  const rlKey = `report:${ip}`;
  if (rateLimited(rlKey)) {
    return bad(429, 'Rate limit exceeded', origin);
  }

  const clean = sanitize(body);
  if (!clean.title || !clean.description) {
    return bad(400, 'Missing required fields: title and description', origin);
  }

  // Compute dedupe key and attach
  const dedupeKey = sha256(`${clean.title}|${clean.type}|${clean.appVersion}|${clean.description.slice(0,200)}`);
  clean.dedupeKey = dedupeKey;

  try {
    const result = await dispatchToGitHub(clean);
    return ok({ status: 'queued', dedupeKey, dryRun: !!process.env.DRY_RUN }, origin);
  } catch (err) {
    return bad(502, err.message || 'Upstream dispatch failed', origin);
  }
};
