# Railway Deployment Troubleshooting

## Quick Fixes for Common Deployment Failures

### Issue: Build fails with "requirements.txt not found"

**Symptom**: Build log shows `ERROR: Could not open requirements file: [Errno 2] No such file or directory: 'requirements.txt'`

**Solution**: Railway needs to find `requirements.txt` in the repository root.

**Verify**:
```bash
# File should exist at repository root
ls -la requirements.txt
```

---

### Issue: Start command fails with "Module not found"

**Symptom**: `ModuleNotFoundError: No module named 'psycopg2'`

**Solution**: Railway didn't install dependencies. Check build logs to ensure pip install ran.

**Railway Build Process Should Show**:
```
Installing dependencies from requirements.txt...
Successfully installed psycopg2-binary-2.9.9 PyJWT-2.8.0 python-dotenv-1.0.0
```

---

### Issue: "DATABASE_URL not set" error

**Symptom**: Application crashes with `DATABASE_URL environment variable not set`

**Solution**:
1. Ensure PostgreSQL service is created in Railway project
2. Check that web service has access to PostgreSQL
3. In Railway, the DATABASE_URL should be automatically populated

**Verify in Railway Settings → Variables**:
- `DATABASE_URL` should show `postgresql://postgres:...`
- If missing, click "+ Reference" and select PostgreSQL's `DATABASE_URL`

---

### Issue: "JWT_SECRET not set" error

**Symptom**: Application crashes with `JWT_SECRET environment variable not set`

**Solution**: Add JWT_SECRET to Railway environment variables

**In Railway Settings → Variables**:
```
JWT_SECRET=f557dc089063ce86e1781ee1f90b9d915c8bba03a1afafb8eae487e8ea38d567
```

---

### Issue: Start command path incorrect

**Symptom**: `python: can't open file 'scripts/api-server-v2.py': [Errno 2] No such file or directory`

**Solution**: Verify the file exists and railway.json has correct path

**Check railway.json**:
```json
{
  "deploy": {
    "startCommand": "python scripts/api-server-v2.py --production --port $PORT"
  }
}
```

**Verify file exists**:
```bash
ls -la scripts/api-server-v2.py
```

---

### Issue: Port binding fails

**Symptom**: `OSError: [Errno 48] Address already in use` or similar

**Solution**: Ensure your app uses Railway's `$PORT` variable

**Correct code in api-server-v2.py**:
```python
port = args.port or int(os.getenv('PORT', '8080'))
```

Railway will set `PORT` automatically - don't hardcode it.

---

### Issue: Health check fails

**Symptom**: "Service unhealthy" - Railway can't reach `/api/health`

**Solution**:
1. Ensure health endpoint responds quickly (< 30 seconds)
2. Verify app binds to `0.0.0.0` not `localhost` in production

**Check in api-server-v2.py**:
```python
if args.production and args.host == "localhost":
    host = "0.0.0.0"  # ✅ Correct for Railway
```

---

## Debug Checklist

When deployment fails, check in this order:

- [ ] **View Railway Logs**: Click "View" on failed deployment
- [ ] **Check Build Logs**: Did dependencies install?
- [ ] **Check Environment Variables**: Are all required vars set?
  - [ ] `DATABASE_URL` (auto from PostgreSQL service)
  - [ ] `JWT_SECRET` (manually added)
  - [ ] `PORT` (auto from Railway)
  - [ ] `CORS_ORIGINS` (manually added)
- [ ] **Check Start Command**: Does `railway.json` point to correct file?
- [ ] **Verify File Exists**: Is `scripts/api-server-v2.py` in repo?
- [ ] **Test Locally**: Does it work with same env vars locally?

---

## Manual Deployment Test (Local)

Test the exact deployment locally before pushing:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set environment variables
export DATABASE_URL="your-railway-postgres-url"
export JWT_SECRET="f557dc089063ce86e1781ee1f90b9d915c8bba03a1afafb8eae487e8ea38d567"
export PORT="8080"
export CORS_ORIGINS="https://pdoom1.com,https://www.pdoom1.com"

# 3. Run the exact start command from railway.json
python scripts/api-server-v2.py --production --port $PORT

# 4. In another terminal, test health endpoint
curl http://localhost:8080/api/health
```

If this works locally, it should work on Railway.

---

## Railway CLI Debug Commands

```bash
# View live logs
railway logs

# Check environment variables
railway variables

# Run shell in Railway environment
railway run bash

# Test database connection
railway run python -c "import os; print(os.getenv('DATABASE_URL'))"
```

---

## Common Error Messages & Solutions

### "psycopg2.OperationalError: could not connect to server"

**Cause**: Database connection failed

**Solutions**:
1. Check DATABASE_URL format: `postgresql://user:pass@host:port/db`
2. Verify PostgreSQL service is running in Railway
3. Check if web service has access to PostgreSQL (should be automatic)

---

### "TypeError: 'NoneType' object is not subscriptable"

**Cause**: Usually DATABASE_URL is None

**Solution**: Reference PostgreSQL's DATABASE_URL in web service variables

---

### "ModuleNotFoundError: No module named 'dotenv'"

**Cause**: Dependencies not installed or wrong Python version

**Solution**:
1. Ensure `requirements.txt` exists in repo root
2. Check Railway build logs for pip install errors
3. Verify Python version compatibility

---

## Railway-Specific Configuration

### Ensure Nixpacks Detects Python

Railway uses Nixpacks for builds. It should auto-detect Python from:
- `requirements.txt`
- `runtime.txt` (optional, for Python version)
- `Procfile` (alternative to railway.json)

### Force Python 3.11 (Optional)

Create `runtime.txt` in repo root:
```
python-3.11
```

### Alternative: Use Procfile Instead of railway.json

Create `Procfile`:
```
web: python scripts/api-server-v2.py --production --port $PORT --host 0.0.0.0
```

---

## Emergency Rollback

If deployment is completely broken:

1. Go to Railway → Deployments
2. Find last working deployment
3. Click "Redeploy"

Or via CLI:
```bash
railway rollback
```

---

## Get Help

If still stuck:

1. **Railway Discord**: https://discord.gg/railway
2. **Railway Docs**: https://docs.railway.app
3. **GitHub Issues**: Post your Railway logs

---

## Success Indicators

You'll know it's working when:

✅ Build log shows: "Installing dependencies from requirements.txt"
✅ Build log shows: "Successfully installed psycopg2-binary PyJWT python-dotenv"
✅ Deployment log shows: "P(Doom)1 Production API Server v2.0.0"
✅ Deployment log shows: "Server: http://0.0.0.0:XXXX"
✅ Health check endpoint responds: `curl https://your-app.railway.app/api/health`
✅ Status shows: "Deployment successful"

---

## Next Steps After Successful Deployment

1. Test health endpoint: `https://your-app.railway.app/api/health`
2. Run database migrations: `railway run python scripts/run_migration.py`
3. Test user registration via curl or Postman
4. Configure custom domain: `api.pdoom1.com`
