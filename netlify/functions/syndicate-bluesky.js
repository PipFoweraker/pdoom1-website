// Netlify Function: syndicate-bluesky
// Posts blog/changelog updates to Bluesky using AT Protocol

exports.handler = async function handler(event) {
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
    
    // Parse the text to find URLs and create facets for rich text
    const facets = [];
    const urlMatch = text.match(/(https?:\/\/[^\s]+)/g);
    if (urlMatch) {
      urlMatch.forEach(foundUrl => {
        const start = text.indexOf(foundUrl);
        const end = start + foundUrl.length;
        facets.push({
          index: {
            byteStart: start,
            byteEnd: end
          },
          features: [{
            $type: 'app.bsky.richtext.facet#link',
            uri: foundUrl
          }]
        });
      });
    }

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
