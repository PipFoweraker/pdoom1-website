# pdoom1-website

Static site + tiny serverless API for pdoom1.

- `public/`: static assets and HTML (index.html, config.json, design/tokens.json)
- `netlify/functions/`: serverless functions (report-bug)
- `.github/workflows/`: CI (bug intake, DreamHost deploy)
- `docs/`: deployment and API docs

## Go-live checklist

See `docs/go-live.md` for a step-by-step sequence covering Netlify API setup, DreamHost deploy, config, and testing.