#!/usr/bin/env bash
set -euo pipefail

# pdoom1-website bootstrap (bash-friendly, safe to re-run)
# - Scaffolds a minimal project structure and placeholder files
# - Initializes a local git repo and makes an initial commit
# - Prints optional commands to create and push a GitHub repo via GH CLI

# Requirements: bash, git. (gh optional for GitHub steps)

command -v git >/dev/null 2>&1 || { echo "git is required (https://git-scm.com/)" >&2; exit 1; }
if ! command -v gh >/dev/null 2>&1; then
  echo "Note: GitHub CLI (gh) not found. You can install it later: https://cli.github.com/"
fi

# Use current directory; don't assume/force a specific parent path.
PROJECT_NAME="pdoom1-website"
CURR_DIR_NAME="$(basename "$(pwd)")"
if [[ "$CURR_DIR_NAME" != "$PROJECT_NAME" ]]; then
  echo "Warning: You're running from '$CURR_DIR_NAME'. Expected '$PROJECT_NAME'. Proceeding anyway..."
fi

# 1) Directories
mkdir -p src/components \
         src/pages \
         src/styles \
         public/images \
         docs \
         .github/workflows \
         netlify/functions \
         api

# 2) Files (created if missing; left untouched if already present)
create_if_absent() { local p="$1"; shift || true; [[ -f "$p" ]] || { printf "%s" "$*" > "$p"; }; }

touch .env.example

authored_year="$(date +%Y 2>/dev/null || echo 2025)"
create_if_absent README.md "# $PROJECT_NAME\n\nShell website scaffold for pdoom1.\n\n- src: components/pages/styles\n- public: static assets (index.html)\n- .github/workflows: CI placeholders\n\n## Next steps\n- Create the GitHub repo and push (see instructions printed by this script).\n- Set any required repo secrets via 'gh secret set'.\n"

create_if_absent .gitignore "# Dependencies\nnode_modules/\n# Builds\ndist/\nbuild/\n# Env\n.env\n.env.*\n# OS/editor\n.DS_Store\nThumbs.db\n.vscode/\n"

create_if_absent public/index.html "<!doctype html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"utf-8\" />\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n  <title>pdoom1</title>\n  <link rel=\"stylesheet\" href=\"/src/styles/main.css\" />\n</head>\n<body>\n  <main>\n    <h1>pdoom1</h1>\n    <p>Welcome. This is the initial shell for the pdoom1 website.</p>\n  </main>\n</body>\n</html>\n"

mkdir -p src/styles
create_if_absent src/styles/main.css "/* Basic starter styles */\n:root { color-scheme: light dark; }\nbody { margin: 0; font: 16px/1.5 system-ui, sans-serif; padding: 2rem; }\nh1 { margin: 0 0 1rem; }\n"

# Optional placeholders matching your idea
create_if_absent package.json "{\n  \"name\": \"$PROJECT_NAME\",\n  \"private\": true,\n  \"version\": \"0.1.0\",\n  \"scripts\": {\n    \"start\": \"python -m http.server -d public 5173\"\n  }\n}\n"

create_if_absent vercel.json "{\n  \"version\": 2\n}\n"

create_if_absent netlify.toml "# Placeholder; configure if you deploy with Netlify\n[build]\n  publish = \"public\"\n"

touch .github/workflows/bug-report.yml
create_if_absent .github/workflows/deploy.yml "# Placeholder GitHub Actions workflow\nname: deploy\n\non: { push: { branches: [ main ] } }\n\njobs:\n  noop:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - run: echo 'Add your deploy steps here'\n"

touch .github/workflows/update-stats.yml

touch server.js

# 3) Git init and first commit
if [[ ! -d .git ]]; then
  git init
fi

git add .
if ! git diff --cached --quiet; then
  git commit -m "chore: scaffold website shell"
else
  echo "Nothing to commit."
fi

echo
echo "Done. Local scaffold is ready." 

echo
if command -v gh >/dev/null 2>&1; then
  echo "Optional: create and push a GitHub repo (requires 'gh auth login' once):"
  echo "  gh repo create $PROJECT_NAME --public --source=. --remote=origin --push"
  echo "\nAfter creation, you can set repo secrets (example):"
  echo "  gh secret set AIRTABLE_API_KEY --body 'your_airtable_key_here'"
  echo "  gh secret set AIRTABLE_BASE_ID --body 'appXXXXXXXXXXXXXX'"
  echo "Note: You do NOT set GITHUB_TOKEN manually; GitHub Actions provides it automatically."
else
  echo "Install GitHub CLI to create the remote easily: https://cli.github.com/"
fi
