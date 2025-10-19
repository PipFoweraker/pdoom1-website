// Netlify Function: syndicate-discord
// Posts blog/changelog updates to Discord via webhook

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

  const { title, text, url, tags = [] } = payload;

  if (!title || !url) {
    return {
      statusCode: 400,
      body: JSON.stringify({ error: 'Missing required fields: title, url' })
    };
  }

  // Get webhook URL from environment
  const webhookUrl = process.env.DISCORD_WEBHOOK_URL;

  if (!webhookUrl) {
    console.error('Discord webhook URL not configured');
    return {
      statusCode: 500,
      body: JSON.stringify({ error: 'Discord webhook not configured' })
    };
  }

  try {
    // Create Discord embed message
    const discordMessage = {
      username: 'p(Doom)1 Updates',
      avatar_url: 'https://pdoom1.com/assets/logo.png', // Optional: add if logo exists
      embeds: [{
        title: title,
        description: text || 'New update available!',
        url: url,
        color: 0x00FF00, // Green color
        fields: tags.length > 0 ? [{
          name: 'Tags',
          value: tags.join(', '),
          inline: false
        }] : [],
        footer: {
          text: 'p(Doom)1 Website',
          icon_url: 'https://pdoom1.com/assets/logo.png' // Optional
        },
        timestamp: new Date().toISOString()
      }]
    };

    // Send to Discord webhook
    const response = await fetch(webhookUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(discordMessage),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Discord webhook failed:', response.status, errorText);
      return {
        statusCode: 502,
        body: JSON.stringify({ error: 'Failed to send Discord notification' })
      };
    }

    // Discord returns 204 No Content on success
    return {
      statusCode: 200,
      body: JSON.stringify({ 
        success: true, 
        platform: 'discord'
      })
    };

  } catch (error) {
    console.error('Discord syndication error:', error);
    return {
      statusCode: 500,
      body: JSON.stringify({ 
        error: 'Internal server error',
        message: error.message 
      })
    };
  }
};
