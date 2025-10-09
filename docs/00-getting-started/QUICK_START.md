# Quick Start Guide - p(Doom)1 Website

## 🚀 Get Running in 5 Minutes

### **Prerequisites**
- **Git**: For version control
- **Python 3.11+**: For local development server
- **Text Editor**: VS Code recommended

### **1. Clone and Setup**
```bash
# Clone the repository
git clone https://github.com/PipFoweraker/pdoom1-website.git
cd pdoom1-website

# Install dependencies (optional, for development scripts)
npm install
```

### **2. Start Local Development**
```bash
# Start local server
npm start
# OR manually:
python -m http.server 8080 --directory public

# Open browser
# Navigate to: http://localhost:8080
```

### **3. Make Your First Change**
```bash
# Edit a file (try the main page)
# File: public/index.html

# Test changes locally
# Refresh browser to see changes
```

### **4. Version and Deploy**
```bash
# For patch changes (0.X.Y → 0.X.Y+1)
# 1. Update version in package.json
# 2. Update public/data/status.json
# 3. Add changelog entry in public/data/website-changes.json

# Commit changes
git add -A
git commit -m "Your change description"

# Create version tag
git tag v0.X.Y -m "Version description"

# Push to GitHub
git push origin main
git push origin v0.X.Y
```

## ⚡ Quick Commands

### **Development**
```bash
npm start                    # Start local server
npm run test:all            # Run all health checks
npm run sync:all            # Update data files
```

### **Testing**
```bash
python scripts/check-version-deployment.py  # Test version detection
python scripts/health-check.py              # Test site health
python scripts/verify-deployment.py         # Test deployment verification
```

### **Deployment**
```bash
# Trigger GitHub Actions deployment
# Go to: GitHub → Actions → "Version-Aware Deployment to DreamHost"
# Click "Run workflow"
```

## 📁 Key Directories

```
pdoom1-website/
├── public/                 # Website files (served directly)
│   ├── index.html         # Main page
│   ├── blog/              # Developer blog
│   ├── assets/            # Images, CSS, etc.
│   └── data/              # JSON data files
├── scripts/               # Automation scripts
├── docs/                  # This documentation
└── .github/workflows/     # GitHub Actions
```

## 🎯 Common Tasks

### **Add a Blog Post**
1. Create: `public/blog/YYYY-MM-DD-title.md`
2. Update: `public/blog/index.json`
3. Follow format in existing posts

### **Update Game Stats**
1. Edit: `public/data/status.json`
2. Update relevant metrics
3. Deploy changes

### **Change Website Design**
1. Edit: `public/assets/css/game-integration.css`
2. Test locally
3. Deploy with version bump

### **Fix a Bug**
1. Identify issue
2. Make fix
3. Test locally
4. Deploy as patch version

## 🔧 Development Tools

### **Local Development**
- **Live Server**: Changes visible immediately
- **Browser DevTools**: Debug CSS and JavaScript
- **Health Checks**: Validate before deployment

### **Version Control**
- **Semantic Versioning**: Major.Minor.Patch
- **Git Tags**: Track releases
- **GitHub Actions**: Automated deployment

### **Deployment**
- **Version-Aware**: Automatic vs manual approval
- **Health Monitoring**: Post-deployment verification
- **Rollback**: Emergency procedures available

## 🆘 Troubleshooting

### **Local Server Won't Start**
```bash
# Check Python version
python --version

# Try different port
python -m http.server 8081 --directory public
```

### **CSS/JS Not Loading**
- Check file paths are correct
- Ensure files are in `public/` directory
- Check browser console for errors

### **Version Conflicts**
- Check `package.json` version matches `public/data/status.json`
- Ensure changelog is updated
- Verify git tags are correct

### **Deployment Issues**
- Check GitHub Actions logs
- Verify environment secrets are set
- Run local health checks first

## 📚 Next Steps

### **Learn More**
- **[PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md)** - Understand the project
- **[WEBSITE_DEVELOPMENT_PROCESS.md](../01-development/WEBSITE_DEVELOPMENT_PROCESS.md)** - Complete development workflow
- **[deployment-guide.md](../02-deployment/deployment-guide.md)** - Production deployment

### **Get Involved**
- **Content**: Add blog posts and updates
- **Design**: Improve styling and user experience
- **Features**: Add new functionality
- **Documentation**: Help improve these guides

### **Advanced Setup**
- **GitHub Environments**: [GITHUB_ENVIRONMENT_SETUP.md](../02-deployment/GITHUB_ENVIRONMENT_SETUP.md)
- **Integration**: [game-repository-integration.md](../03-integrations/game-repository-integration.md)
- **Content Pipeline**: [content-pipeline.md](../01-development/content-pipeline.md)

**You're ready to go!** 🎉 

Start with local development, make small changes, and gradually work up to more complex features and deployments.