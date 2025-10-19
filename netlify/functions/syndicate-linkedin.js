// Netlify Function: syndicate-linkedin
// Posts blog/changelog updates to LinkedIn using UGC Post API

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

  if (!text || !url) {
    return {
      statusCode: 400,
      body: JSON.stringify({ error: 'Missing required fields: text, url' })
    };
  }

  // Get credentials from environment
  const accessToken = process.env.LINKEDIN_ACCESS_TOKEN;
  const orgId = process.env.LINKEDIN_ORG_ID; // URN format: urn:li:organization:108743037

  if (!accessToken || !orgId) {
    console.error('LinkedIn credentials not configured');
    return {
      statusCode: 500,
      body: JSON.stringify({ error: 'LinkedIn credentials not configured' })
    };
  }

  try {
    // Ensure orgId is in URN format
    const authorUrn = orgId.startsWith('urn:li:organization:') 
      ? orgId 
      : `urn:li:organization:${orgId}`;

    // Create LinkedIn UGC post
    const postData = {
      author: authorUrn,
      lifecycleState: 'PUBLISHED',
      specificContent: {
        'com.linkedin.ugc.ShareContent': {
          shareCommentary: {
            text: text
          },
          shareMediaCategory: 'ARTICLE',
          media: [
            {
              status: 'READY',
              originalUrl: url,
              title: {
                text: title || 'New Update'
              }
            }
          ]
        }
      },
      visibility: {
        'com.linkedin.ugc.MemberNetworkVisibility': 'PUBLIC'
      }
    };

    const response = await fetch('https://api.linkedin.com/v2/ugcPosts', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'X-Restli-Protocol-Version': '2.0.0',
      },
      body: JSON.stringify(postData),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('LinkedIn API error:', response.status, errorText);
      return {
        statusCode: 502,
        body: JSON.stringify({ 
          error: 'Failed to post to LinkedIn',
          details: errorText
        })
      };
    }

    const result = await response.json();

    return {
      statusCode: 200,
      body: JSON.stringify({ 
        success: true, 
        platform: 'linkedin',
        postId: result.id
      })
    };

  } catch (error) {
    console.error('LinkedIn syndication error:', error);
    return {
      statusCode: 500,
      body: JSON.stringify({ 
        error: 'Internal server error',
        message: error.message 
      })
    };
  }
};
