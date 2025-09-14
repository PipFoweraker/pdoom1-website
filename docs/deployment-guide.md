# Deployment Guide - DreamHost via GitHub Actions

This is the standard deployment process for all p(Doom)1 repositories that need web hosting.

## Prerequisites

- DreamHost shared hosting account
- GitHub repository with appropriate permissions
- SSH key pair for DreamHost access

## One-Time Setup

### 1. DreamHost Setup

1. **Create Shell User**:
   - DreamHost Panel → Users → Manage Users
   - Create new user or modify existing user to enable "Shell User" (not just SFTP)
   - Note the username (format: `domainname_shell` or similar)

2. **Upload SSH Public Key**:
   - SSH into DreamHost or use File Manager
   - Navigate to `~/.ssh/` directory
   - Add your public key to `authorized_keys` file
   - Set permissions: `chmod 600 ~/.ssh/authorized_keys`

3. **Verify Domain Setup**:
   - Ensure your domain points to the correct directory
   - Standard path: `/home/username/yourdomain.com/`

### 2. GitHub Repository Secrets

Add these secrets in GitHub repo settings → Secrets and variables → Actions:

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `DH_HOST` | Your domain name | `pdoom1.com` |
| `DH_USER` | DreamHost shell username | `pdoom1_dot_com_shell` |
| `DH_PATH` | Full path to web root | `/home/pdoom1_dot_com_shell/pdoom1.com` |
| `DH_SSH_KEY` | Private SSH key content | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `DH_PORT` (optional) | SSH port if non-standard | `22` |

### 3. Repository Structure

Ensure your repository has:
```
.github/
  workflows/
    deploy-dreamhost.yml    # Deployment workflow
public/                     # Static files to deploy
docs/
  deployment-guide.md       # This guide
```

## Deployment Process

### Standard Deployment

1. Go to GitHub repository → Actions tab
2. Select "Deploy to DreamHost (manual)" workflow
3. Click "Run workflow"
4. Choose branch (usually `main`)
5. Leave "dry run" unchecked for actual deployment
6. Click "Run workflow"

### Test Deployment (Dry Run)

1. Follow same steps as above
2. **Check "Run rsync with --dry-run"** option
3. Review the workflow output to see what would be changed
4. Run actual deployment if satisfied

## How It Works

The workflow:
1. Checks out your repository code
2. Sets up SSH authentication using your private key
3. Ensures the remote directory exists
4. Uses `rsync` to sync `public/` folder to DreamHost
5. Uses `--delete` flag to remove files not in source

## Troubleshooting

### Common Issues

**SSH Connection Failed**:
- Verify SSH key is correctly added to DreamHost
- Check that user has Shell access (not just SFTP)
- Confirm `DH_HOST`, `DH_USER`, and `DH_PATH` secrets are correct

**Permission Denied**:
- SSH key permissions: `chmod 600 ~/.ssh/authorized_keys` on DreamHost
- Verify the shell user owns the target directory

**Files Not Appearing**:
- Check `DH_PATH` points to correct web root
- Verify domain DNS and DreamHost domain setup
- Check file permissions on deployed files

### Manual Testing

Test SSH connection locally:
```bash
ssh -i /path/to/private/key username@domain.com "pwd && ls -la"
```

### Workflow Logs

- Check GitHub Actions tab for detailed logs
- Look for rsync output showing transferred files
- Verify no permission or connection errors

## Security Best Practices

1. **SSH Keys**:
   - Use dedicated SSH key pair for deployment
   - Never commit private keys to repository
   - Rotate keys periodically

2. **GitHub Secrets**:
   - Limit secret access to necessary environments
   - Use environment protection rules for production
   - Review secret usage regularly

3. **DreamHost**:
   - Use least-privilege shell user
   - Monitor deployment logs
   - Keep DreamHost account secure

## Repository Standards

All p(Doom)1 repositories should:
- Use this exact workflow file (`.github/workflows/deploy-dreamhost.yml`)
- Follow the same secret naming convention
- Include this documentation
- Use `public/` folder for deployable static content
- Test with dry-run before production deployments

## API Configuration

For sites with API endpoints (like bug reporting):
- Keep APIs on Netlify for better serverless handling
- Set `apiBase` in `public/config.json` to Netlify URL
- Configure CORS properly between DreamHost and Netlify

Example `public/config.json`:
```json
{
  "apiBase": "https://pdoom1-website-app.netlify.app",
  "contactEmail": "team@pdoom1.com"
}
```

## Support

- Check workflow logs first
- Test SSH connection manually
- Verify all secrets are set correctly
- Consult DreamHost documentation for hosting-specific issues
