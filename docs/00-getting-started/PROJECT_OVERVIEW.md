# p(Doom)1 Website - Project Overview

## 🎯 What Is This Project?

The **p(Doom)1 Website** is the official web presence for the p(Doom)1 AI Safety strategy game. It serves as:

- **Game Information Hub**: Details about gameplay, features, and download links
- **Developer Blog**: Technical insights and development progress  
- **Community Portal**: Bug reporting, feedback, and engagement
- **Professional Showcase**: Demonstrates our development capabilities

## 🏗️ Architecture Overview

### **Frontend**
- **Static Website**: HTML, CSS, JavaScript (no framework dependencies)
- **Game-Integrated Design**: Authentic p(Doom)1 visual identity
- **Mobile-Responsive**: Works on all devices and screen sizes
- **Progressive Enhancement**: Core functionality works without JavaScript

### **Content Management**
- **JSON-Based**: Content stored in structured JSON files
- **Git-Versioned**: All content tracked in version control
- **Developer-Friendly**: No CMS complexity, direct file editing

### **Deployment**
- **GitHub Actions**: Automated CI/CD pipeline
- **DreamHost Hosting**: Production hosting with rsync deployment
- **Version-Aware**: Automatic patch deployment, manual approval for major changes
- **Health Monitoring**: Automated verification and rollback capabilities

## 🔄 Development Workflow

### **Standard Updates**
1. **Local Development**: Test changes locally
2. **Version Control**: Commit with semantic versioning
3. **Automated Deployment**: GitHub Actions handles deployment
4. **Verification**: Automated health checks confirm success

### **Major Changes**
1. **Development**: Create and test significant changes
2. **Version Bump**: Update to major version (X.0.0)
3. **Manual Approval**: GitHub workflow requires reviewer approval
4. **Deployment**: Only proceeds after human review

## 🎨 Design Philosophy

### **Game Integration**
- **Authentic Colors**: Uses actual p(Doom)1 color palette
- **Retro Gaming Aesthetic**: Buttons, fonts, and UI elements match game style
- **Professional Polish**: Game styling with modern web standards

### **User Experience**
- **Keyboard Navigation**: Comprehensive shortcuts for power users
- **Quick Actions**: Floating menu with common tasks
- **Breadcrumb Navigation**: Clear site hierarchy
- **Mobile-First**: Touch-friendly interactions

## 🔗 Project Relationships

### **p(Doom)1 Game Repository**
- **Content Source**: Game changelog and release information
- **Asset Integration**: Shared visual design and branding
- **Development Sync**: Website reflects game development progress

### **Bug Reporting System**
- **GitHub Issues**: Automated issue creation from website forms
- **Netlify Functions**: Serverless form processing
- **Community Engagement**: Direct player feedback integration

### **Documentation Ecosystem**
- **Multi-Repository**: Coordinates with game and data repositories
- **Cross-Referencing**: Links between related documentation
- **Unified Strategy**: Consistent documentation approach

## 📊 Current Capabilities

### **Content Types**
- **Landing Page**: Game overview and download links
- **Developer Blog**: Technical posts with real development insights
- **Game Statistics**: Dynamic stats and metrics
- **Changelog Systems**: Separate website and game change tracking

### **Technical Features**
- **Version-Aware Deployment**: Smart deployment based on semantic versioning
- **Health Monitoring**: Automated checks and verification
- **Error Boundaries**: Graceful degradation and recovery
- **Performance Optimization**: Fast loading and minimal dependencies

### **Developer Experience**
- **Local Development**: Simple Python HTTP server
- **Hot Reloading**: Fast iteration cycle
- **Automated Testing**: Health checks and deployment verification
- **Documentation**: Comprehensive guides and processes

## 🚀 Getting Started

### **For Developers**
1. **Clone Repository**: `git clone https://github.com/PipFoweraker/pdoom1-website.git`
2. **Follow Quick Start**: [QUICK_START.md](./QUICK_START.md)
3. **Read Development Process**: [01-development/WEBSITE_DEVELOPMENT_PROCESS.md](../01-development/WEBSITE_DEVELOPMENT_PROCESS.md)

### **For Content Contributors**
1. **Understand Content Pipeline**: [01-development/content-pipeline.md](../01-development/content-pipeline.md)
2. **Follow Style Guide**: [01-development/style-guide.md](../01-development/style-guide.md)
3. **Create Blog Posts**: Use established formats and metadata

### **For Deployment**
1. **Configure Environments**: [02-deployment/GITHUB_ENVIRONMENT_SETUP.md](../02-deployment/GITHUB_ENVIRONMENT_SETUP.md)
2. **Set Up Secrets**: Add DreamHost credentials
3. **Test Deployment**: Start with patch version changes

## 🎯 Success Metrics

### **Technical Goals**
- ✅ **Sub-second Load Times**: Fast, responsive website
- ✅ **100% Uptime**: Reliable hosting and monitoring
- ✅ **Mobile Responsive**: Works on all devices
- ✅ **Accessibility**: ARIA labels and keyboard navigation

### **Content Goals**
- ✅ **Regular Updates**: Weekly blog posts during active development
- ✅ **Professional Quality**: Technical content suitable for professional sharing
- ✅ **Game Integration**: Authentic representation of game project
- ✅ **Community Engagement**: Active bug reporting and feedback

### **Development Goals**
- ✅ **Safe Deployments**: Version-aware deployment with manual approval gates
- ✅ **Documentation**: Complete, organized, and maintained documentation
- ✅ **Developer Experience**: Simple setup and contribution process
- ✅ **Process Automation**: Minimal manual work for routine tasks

This project demonstrates professional web development practices while maintaining the authentic character of the p(Doom)1 game project.