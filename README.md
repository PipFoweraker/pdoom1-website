# p(Doom)1 Website

Professional website for the p(Doom)1 AI Safety Strategy Game. Features real-time leaderboards, comprehensive game documentation, and a polished user experience.

## 🚀 Live Site

**Production:** https://pdoom1.com  
**Development:** Auto-deployed from dev branch

## 🏗️ Architecture

### Frontend
- **Static Site**: Pure HTML/CSS/JS for maximum performance
- **Responsive Design**: Mobile-first approach with terminal aesthetic
- **Progressive Enhancement**: Works without JavaScript
- **Accessibility**: WCAG compliant with ARIA support

### Backend
- **Serverless Functions**: Netlify Functions for form handling
- **Real-time Data**: JSON APIs for leaderboard integration
- **Multi-platform Deploy**: DreamHost + Netlify hybrid approach

### Key Features
- **Navigation System**: Clean dropdown menus with keyboard support
- **Leaderboard Integration**: Real-time game data from Python backend
- **Professional Polish**: SEO optimized, structured data, social cards
- **Developer Tools**: Automated testing and deployment workflows

## 📁 Project Structure

```
pdoom1-website/
├── public/                 # Static website files
│   ├── index.html         # Main homepage
│   ├── about/             # About page and team info
│   ├── blog/              # Development blog posts
│   ├── leaderboard/       # Player rankings and stats
│   ├── docs/              # Game documentation
│   ├── press/             # Media kit (hidden until release)
│   ├── assets/            # Images, icons, screenshots
│   └── data/              # JSON APIs and content
├── netlify/functions/     # Serverless backend functions
├── scripts/               # Development and deployment tools
├── docs/                  # Technical documentation
└── .github/workflows/     # CI/CD automation
```

## 🛠️ Development

### Prerequisites
- Python 3.8+ (for local server)
- Git (for version control)
- GitHub CLI (for deployment)

### Local Development
```bash
# Clone the repository
git clone https://github.com/PipFoweraker/pdoom1-website.git
cd pdoom1-website

# Start local development server
python -m http.server 8000 --directory public

# Open in browser
open http://localhost:8000
```

### Testing
```bash
# Run header consistency tests
bash scripts/test-header-consistency.sh

# Check for common issues
scripts/validate-deployment.sh
```

## 🚢 Deployment

### Automatic Deployment
- **Main Branch** → DreamHost production
- **Dev Branch** → Netlify preview
- **Pull Requests** → Netlify deploy previews

### Manual Deployment
```bash
# Deploy to DreamHost
gh workflow run deploy-dreamhost.yml

# Check deployment status
gh run list --workflow="deploy-dreamhost.yml" --limit 3
```

## 📋 Content Management

### Blog Posts
1. Create `.md` file in `public/blog/`
2. Update `public/data/blog.json` with metadata
3. Posts auto-appear on blog page

### Leaderboard Data
- **Source**: Main p(Doom)1 game repository
- **Format**: JSON with comprehensive game metrics
- **Updates**: Real-time via game completion hooks

### Game Documentation
- **Location**: `public/docs/`
- **Integration**: Links to main repository docs
- **Status**: Live game data integration

## 🎨 Design System

### Color Scheme
- **Primary**: `#00ff41` (Matrix Green)
- **Secondary**: `#ff6b35` (Warning Orange)
- **Background**: `#1a1a1a` (Dark Terminal)
- **Text**: `#ffffff` / `#cccccc` / `#888888`

### Typography
- **Primary**: Courier New (monospace)
- **Aesthetic**: Terminal/retro computing
- **Hierarchy**: Clear size and weight distinctions

### Components
- Dropdown navigation with hover states
- Card-based content layouts
- Professional form styling
- Responsive breakpoints

## 🔧 Configuration

### Environment Variables
- Deployment handled via GitHub Actions
- Secrets managed in repository settings
- No local environment file needed for basic development

### API Endpoints
- `/data/status.json` - Game status and version info
- `/data/blog.json` - Blog post metadata
- `/leaderboard/data/leaderboard.json` - Player rankings
- `/.netlify/functions/report-bug` - Bug report submission

## 📚 Documentation

### For Developers
- [`docs/deployment-guide.md`](docs/deployment-guide.md) - Full deployment setup
- [`docs/integration-plan.md`](docs/integration-plan.md) - Game integration architecture
- [`docs/leaderboard-integration-spec.md`](docs/leaderboard-integration-spec.md) - Leaderboard system

### For Content
- [`docs/style-guide.md`](docs/style-guide.md) - Writing and design standards
- [`docs/content-pipeline.md`](docs/content-pipeline.md) - Content workflow

### For Deployment
- [`docs/deploy-dreamhost.md`](docs/deploy-dreamhost.md) - DreamHost setup
- [`docs/go-live.md`](docs/go-live.md) - Launch checklist

## 🤝 Contributing

### Code Standards
- Follow existing code style and structure
- Test changes locally before committing
- Use semantic commit messages
- Update documentation for major changes

### Content Guidelines
- Maintain professional tone
- Use consistent terminology
- Include relevant tags and metadata
- Optimize for both users and search engines

## 📊 Analytics & Performance

### Metrics
- Page load times < 2 seconds
- Accessibility score: AAA
- SEO optimization: Full
- Mobile responsiveness: Complete

### Monitoring
- GitHub Actions for deployment health
- Manual testing across browsers/devices
- Performance audits via dev tools

## 🗺️ Roadmap

### Completed ✅
- Professional navigation system
- Real-time leaderboard integration
- Comprehensive SEO optimization
- Accessibility compliance
- Multi-platform deployment

### In Progress 🔄
- Game screenshot integration
- Additional blog content
- Performance optimizations

### Future 🔮
- WebSocket real-time updates
- Player profile pages
- Advanced analytics integration
- Community features

## 📄 License

This website is part of the p(Doom)1 project. See the main game repository for licensing information.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/PipFoweraker/pdoom1-website/issues)
- **Game Issues**: [Main Repository](https://github.com/PipFoweraker/pdoom1/issues)
- **Contact**: Via website contact form

---

Built with care for the AI Safety community. 🤖⚡