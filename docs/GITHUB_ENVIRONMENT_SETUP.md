# GitHub Environment Setup for Version-Aware Deployment

## Overview
To enable version-aware deployments with manual approval gates, you need to configure GitHub environments.

## Required Environments

### 1. production-approval
**Purpose**: Manual approval gate for major version changes
**Protection Rules**:
- Required reviewers: Repository maintainers
- Wait timer: 0 minutes
- Prevent administrators from bypassing: No (for flexibility)

### 2. production  
**Purpose**: Production deployment environment
**Protection Rules**:
- Required reviewers: Optional (already gated by production-approval)
- Deployment branches: main branch only
- Environment variables: All DreamHost secrets

## Setup Instructions

### Step 1: Access Environment Settings
1. Go to your repository on GitHub
2. Click **Settings** tab
3. Click **Environments** in the left sidebar
4. Click **New environment**

### Step 2: Create production-approval Environment
1. Name: `production-approval`
2. Configure protection rules:
   - ✅ **Required reviewers**: Add yourself and any other maintainers
   - ⚠️ **Wait timer**: 0 minutes
   - Environment secrets: None needed
3. Click **Save protection rules**

### Step 3: Create production Environment  
1. Name: `production`
2. Configure protection rules:
   - **Required reviewers**: Optional (recommended for additional safety)
   - **Deployment branches**: Select "Selected branches" → Add `main`
3. Add environment secrets:
   - `DH_HOST`: Your DreamHost hostname
   - `DH_USER`: Your DreamHost username  
   - `DH_PATH`: Your DreamHost deployment path
   - `DH_SSH_KEY`: Your DreamHost SSH private key
   - `DH_PORT`: Your DreamHost SSH port (usually 22)
4. Click **Save protection rules**

## How It Works

### Automatic Deployment (Patch/Minor Changes)
- Version change detected as patch or minor
- Pre-deployment checks run automatically
- Deployment proceeds without manual approval
- Post-deployment verification runs

### Manual Approval Required (Major Changes)
- Version change detected as major (X.0.0)
- Workflow pauses at `production-approval` environment
- GitHub sends notification to required reviewers
- Reviewer must manually approve the deployment
- Only then does deployment proceed

### Force Deployment Option
- Use `force_deploy: true` input to bypass version checks
- Use `skip_version_check: true` for emergency deployments
- Still requires environment protection rules

## Version Change Detection

### Major (X.0.0)
- **Triggers**: Manual approval required
- **Requirements**: Changelog updated, blog post recommended
- **Example**: 0.2.0 → 1.0.0

### Minor (0.X.0)  
- **Triggers**: Automatic deployment with checks
- **Requirements**: Changelog updated, blog post recommended
- **Example**: 0.2.0 → 0.3.0

### Patch (0.0.X)
- **Triggers**: Automatic deployment
- **Requirements**: Changelog updated
- **Example**: 0.2.0 → 0.2.1

## Manual Approval Process

### When Approval is Required
1. Workflow triggers and detects major version change
2. Version check job completes with `requires_manual_approval: true`
3. Workflow pauses at `manual_approval` job
4. GitHub sends notification to configured reviewers

### How to Approve
1. Go to **Actions** tab in GitHub repository
2. Click on the pending workflow run
3. Click **Review deployments** button
4. Select `production-approval` environment
5. Add optional comment explaining approval
6. Click **Approve and deploy**

### What Reviewers Should Check
- [ ] Version change is intentional and documented
- [ ] Changelog has been updated for this version
- [ ] Blog post exists or is planned for major changes
- [ ] Breaking changes are documented
- [ ] Deployment notes explain the change

## Emergency Procedures

### Emergency Deployment
If you need to deploy urgently bypassing normal checks:

1. Use workflow dispatch with `force_deploy: true`
2. Add detailed explanation in `deployment_notes`
3. Still requires environment approval if configured

### Rollback Procedure
If deployment fails or causes issues:

1. Revert changes in git: `git revert <commit>`
2. Update version in package.json if needed
3. Deploy with normal process or force deployment
4. Update incident documentation

## Monitoring and Alerts

### Post-Deployment Checks
- Health check validation
- Deployment verification script
- Site accessibility verification

### Failure Handling
- Deployment failures are logged in GitHub Actions
- Post-deployment verification failures are reported
- Manual investigation required for failures

## Security Considerations

### Secret Management
- All DreamHost credentials stored as GitHub environment secrets
- Secrets are only accessible during deployment jobs
- Environment protection prevents unauthorized deployments

### Access Control
- Only repository collaborators can trigger deployments
- Manual approval requires designated reviewers
- Audit trail maintained in GitHub Actions logs

## Testing the Setup

### Test Patch Deployment
1. Make minor change and update patch version (e.g., 0.2.0 → 0.2.1)
2. Commit and push
3. Trigger deployment - should proceed automatically

### Test Major Version Approval
1. Update major version (e.g., 0.2.0 → 1.0.0)  
2. Trigger deployment
3. Verify manual approval is required
4. Test approval process

This setup ensures that significant version changes get proper review while allowing routine updates to deploy automatically.