// Shared authentication gate for the syndication endpoints.
//
// WHY THIS EXISTS
// ---------------
// The syndicate-* functions are deployed and publicly reachable. Before this,
// any of them would accept an unauthenticated POST from anyone and post the
// supplied text to the project's own social accounts. The function URLs are
// discoverable -- they are in a public repository. So the moment a credential
// like BLUESKY_APP_PASSWORD was set, the account was open to the internet.
//
// Every syndication handler must call requireAuth(event) FIRST and return
// immediately if it returns a response.
//
// The shared secret lives in SYNDICATION_TOKEN, set in the Netlify site
// environment (where the function reads it) AND as a GitHub secret (where the
// workflow sends it from). Both are required; setting only one produces a green
// workflow and a 401 from the function.

const crypto = require('crypto');

const HEADER = 'x-syndication-token';

/**
 * Constant-time string comparison. A plain `===` on a secret leaks its prefix
 * through timing, which is cheap to avoid and awkward to explain afterwards.
 */
function safeEqual(a, b) {
  const ba = Buffer.from(String(a), 'utf8');
  const bb = Buffer.from(String(b), 'utf8');
  // timingSafeEqual throws on length mismatch, which is itself a length oracle.
  // Hash both sides first so the compared buffers are always the same size.
  const ha = crypto.createHash('sha256').update(ba).digest();
  const hb = crypto.createHash('sha256').update(bb).digest();
  return crypto.timingSafeEqual(ha, hb);
}

/**
 * @returns {object|null} a Netlify response to return immediately, or null if
 *                        the caller is authorised.
 */
function requireAuth(event) {
  const expected = process.env.SYNDICATION_TOKEN;

  // Fail CLOSED. If the token is not configured, refuse every request rather
  // than falling back to open -- an unconfigured gate must never mean "allow".
  if (!expected) {
    console.error('SYNDICATION_TOKEN is not set; refusing all requests');
    return {
      statusCode: 503,
      body: JSON.stringify({
        error: 'Syndication is not configured',
        hint: 'Set SYNDICATION_TOKEN in the Netlify site environment'
      })
    };
  }

  const headers = event.headers || {};
  // Netlify lowercases header names, but do not rely on it.
  const supplied = headers[HEADER] ||
                   headers[HEADER.toUpperCase()] ||
                   Object.entries(headers)
                     .find(([k]) => k.toLowerCase() === HEADER)?.[1];

  if (!supplied || !safeEqual(supplied, expected)) {
    console.warn('Rejected syndication request with missing/invalid token');
    return {
      statusCode: 401,
      body: JSON.stringify({ error: 'Unauthorized' })
    };
  }

  return null;
}

module.exports = { requireAuth, HEADER };
