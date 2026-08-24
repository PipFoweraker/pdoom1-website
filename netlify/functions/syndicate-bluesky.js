// Netlify Function: syndicate-bluesky
// Posts blog/changelog updates to Bluesky using AT Protocol

const { requireAuth } = require('./_auth');

// A facet index is measured in UTF-8 BYTES, not in JavaScript string positions.
//
// This got it wrong until 2026-08-24. It used `text.indexOf(url)` -- a UTF-16
// code-unit index -- directly as `byteStart`. The two agree only while the text
// before the URL is pure ASCII, which every auto-generated draft happens to be,
// so the bug was invisible: measured on the four drafts in content/syndication/
// the two indices matched exactly. One em dash ahead of the link moves them
// apart by two, one emoji by three, and the facet then covers the wrong span --
// the post publishes with a link that points at nothing, or at a fragment of
// the sentence. The syndication workflow exists to let a human edit copy before
// approving it, and the campaign copy this project writes is full of em dashes,
// so the first hand-edited post is exactly where it would have shown up.
//
// Two more defects went with it, both from the same three lines:
//   - `String.match(/g)` returns the matched TEXT, and `indexOf` then finds the
//     FIRST occurrence. A URL repeated in one post produced two facets pointing
//     at the same span, and none at the second occurrence. `regex.exec` in a
//     loop yields each match's own position, so repeats are handled by
//     construction rather than by remembering to handle them.
//   - `[^\s]+` swallows sentence punctuation, so "see https://pdoom1.com/." put
//     the full stop inside the href. Trailing `.,;:!?` and quotes are trimmed.
//     A closing bracket is trimmed ONLY when the URL carries no matching
//     opener, because `en.wikipedia.org/wiki/Doom_(1993)` is a real URL whose
//     bracket belongs to it -- trimming that would break more links than it fixes.
const TRAILING_PUNCTUATION = /[.,;:!?'"]+$/;

function trimTrailing(url) {
  let out = url.replace(TRAILING_PUNCTUATION, '');
  // Unbalanced closers only. Repeat so "foo)]." settles rather than needing one
  // pass per character class.
  for (;;) {
    const last = out.slice(-1);
    const opener = { ')': '(', ']': '[', '}': '{' }[last];
    if (!opener) break;
    const opens = out.split(opener).length - 1;
    const closes = out.split(last).length - 1;
    if (closes <= opens) break;          // balanced: the bracket is part of the URL
    out = out.slice(0, -1).replace(TRAILING_PUNCTUATION, '');
  }
  return out;
}

/**
 * Build AT Protocol link facets for every URL in `text`.
 *
 * Exported so scripts/test-syndication-facets.js drives the SAME code the
 * handler runs. A test against a re-implementation would only prove the copy
 * agrees with itself.
 *
 * @param {string} text
 * @returns {Array} facets, in order of appearance; empty when there are no URLs.
 */
function linkFacets(text) {
  const facets = [];
  const pattern = /https?:\/\/[^\s]+/g;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    const uri = trimTrailing(match[0]);
    if (!uri) continue;
    const byteStart = Buffer.byteLength(text.slice(0, match.index), 'utf8');
    facets.push({
      index: {
        byteStart,
        byteEnd: byteStart + Buffer.byteLength(uri, 'utf8')
      },
      features: [{
        $type: 'app.bsky.richtext.facet#link',
        uri
      }]
    });
  }
  return facets;
}

exports.handler = async function handler(event) {
  // Auth FIRST -- before parsing, before touching credentials. These endpoints
  // are publicly reachable and post to real accounts.
  const denied = requireAuth(event);
  if (denied) return denied;

  // Only allow POST requests
  if (event.httpMethod !== 'POST') {
    return {
      statusCode: 405,
      body: JSON.stringify({ error: 'Method Not Allowed' })
    };
  }

  // Parse request body
  let payload;
  try {
    payload = JSON.parse(event.body || '{}');
  } catch (e) {
    return {
      statusCode: 400,
      body: JSON.stringify({ error: 'Invalid JSON body' })
    };
  }

  const { title, text, url } = payload;

  if (!title || !text || !url) {
    return {
      statusCode: 400,
      body: JSON.stringify({ error: 'Missing required fields: title, text, url' })
    };
  }

  // Get credentials from environment
  const handle = process.env.BLUESKY_HANDLE;
  const appPassword = process.env.BLUESKY_APP_PASSWORD;

  if (!handle || !appPassword) {
    console.error('Bluesky credentials not configured');
    return {
      statusCode: 500,
      body: JSON.stringify({ error: 'Bluesky credentials not configured' })
    };
  }

  try {
    // Step 1: Create session (login)
    const sessionResponse = await fetch('https://bsky.social/xrpc/com.atproto.server.createSession', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        identifier: handle,
        password: appPassword,
      }),
    });

    if (!sessionResponse.ok) {
      const errorText = await sessionResponse.text();
      console.error('Bluesky session creation failed:', errorText);
      return {
        statusCode: 502,
        body: JSON.stringify({ error: 'Failed to authenticate with Bluesky' })
      };
    }

    const session = await sessionResponse.json();
    const accessJwt = session.accessJwt;
    const did = session.did;

    // Step 2: Create post
    const now = new Date().toISOString();
    
    // Parse the text to find URLs and create facets for rich text.
    // See linkFacets() above for why this is not inline any more.
    const facets = linkFacets(text);

    const postData = {
      repo: did,
      collection: 'app.bsky.feed.post',
      record: {
        $type: 'app.bsky.feed.post',
        text: text,
        facets: facets.length > 0 ? facets : undefined,
        createdAt: now,
      },
    };

    const postResponse = await fetch('https://bsky.social/xrpc/com.atproto.repo.createRecord', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${accessJwt}`,
      },
      body: JSON.stringify(postData),
    });

    if (!postResponse.ok) {
      const errorText = await postResponse.text();
      console.error('Bluesky post creation failed:', errorText);
      return {
        statusCode: 502,
        body: JSON.stringify({ error: 'Failed to create post on Bluesky' })
      };
    }

    const postResult = await postResponse.json();

    return {
      statusCode: 200,
      body: JSON.stringify({ 
        success: true, 
        platform: 'bluesky',
        uri: postResult.uri,
        cid: postResult.cid
      })
    };

  } catch (error) {
    console.error('Bluesky syndication error:', error);
    return {
      statusCode: 500,
      body: JSON.stringify({ 
        error: 'Internal server error',
        message: error.message 
      })
    };
  }
};

// Exported for scripts/test-syndication-facets.js. The handler above uses the
// same function, so the test cannot pass against a divergent copy.
exports.linkFacets = linkFacets;
