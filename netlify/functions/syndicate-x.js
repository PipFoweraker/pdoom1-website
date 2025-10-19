// Netlify Function: syndicate-x
// Posts blog/changelog updates to X (Twitter) using API v2

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

  const { text } = payload;

  if (!text) {
    return {
      statusCode: 400,
      body: JSON.stringify({ error: 'Missing required field: text' })
    };
  }

  // Get credentials from environment
  // For X API v2, we can use OAuth 2.0 Bearer Token or OAuth 1.0a
  const bearerToken = process.env.TWITTER_BEARER_TOKEN;
  const apiKey = process.env.TWITTER_API_KEY;
  const apiSecret = process.env.TWITTER_API_SECRET;
  const accessToken = process.env.TWITTER_ACCESS_TOKEN;
  const accessSecret = process.env.TWITTER_ACCESS_SECRET;

  // Check if we have bearer token (simpler) or OAuth 1.0a credentials
  if (!bearerToken && (!apiKey || !apiSecret || !accessToken || !accessSecret)) {
    console.error('Twitter credentials not configured');
    return {
      statusCode: 500,
      body: JSON.stringify({ error: 'Twitter credentials not configured' })
    };
  }

  try {
    let response;

    if (bearerToken) {
      // Use OAuth 2.0 Bearer Token (simpler but read-only for most endpoints)
      // For posting tweets, we actually need OAuth 1.0a or OAuth 2.0 with user context
      // This is a placeholder - actual implementation would need proper OAuth 2.0 flow
      console.warn('Bearer token alone cannot post tweets - OAuth 1.0a required');
      return {
        statusCode: 501,
        body: JSON.stringify({ 
          error: 'Twitter posting requires OAuth 1.0a credentials',
          message: 'Please configure TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, and TWITTER_ACCESS_SECRET'
        })
      };
    }

    // OAuth 1.0a implementation (requires crypto library for signature)
    const crypto = require('crypto');
    
    // Generate OAuth 1.0a signature
    const oauthNonce = crypto.randomBytes(16).toString('hex');
    const oauthTimestamp = Math.floor(Date.now() / 1000).toString();
    
    const oauthParams = {
      oauth_consumer_key: apiKey,
      oauth_nonce: oauthNonce,
      oauth_signature_method: 'HMAC-SHA1',
      oauth_timestamp: oauthTimestamp,
      oauth_token: accessToken,
      oauth_version: '1.0'
    };

    // Create signature base string
    const paramString = Object.keys(oauthParams)
      .sort()
      .map(key => `${encodeURIComponent(key)}=${encodeURIComponent(oauthParams[key])}`)
      .join('&');
    
    const signatureBase = [
      'POST',
      encodeURIComponent('https://api.twitter.com/2/tweets'),
      encodeURIComponent(paramString)
    ].join('&');

    // Create signing key and generate signature
    const signingKey = `${encodeURIComponent(apiSecret)}&${encodeURIComponent(accessSecret)}`;
    const signature = crypto
      .createHmac('sha1', signingKey)
      .update(signatureBase)
      .digest('base64');

    oauthParams.oauth_signature = signature;

    // Build Authorization header
    const authHeader = 'OAuth ' + Object.keys(oauthParams)
      .sort()
      .map(key => `${encodeURIComponent(key)}="${encodeURIComponent(oauthParams[key])}"`)
      .join(', ');

    // Post tweet using Twitter API v2
    response = await fetch('https://api.twitter.com/2/tweets', {
      method: 'POST',
      headers: {
        'Authorization': authHeader,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        text: text
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Twitter API error:', response.status, errorText);
      return {
        statusCode: 502,
        body: JSON.stringify({ 
          error: 'Failed to post to Twitter',
          details: errorText
        })
      };
    }

    const result = await response.json();

    return {
      statusCode: 200,
      body: JSON.stringify({ 
        success: true, 
        platform: 'twitter',
        tweetId: result.data?.id,
        text: result.data?.text
      })
    };

  } catch (error) {
    console.error('Twitter syndication error:', error);
    return {
      statusCode: 500,
      body: JSON.stringify({ 
        error: 'Internal server error',
        message: error.message 
      })
    };
  }
};
