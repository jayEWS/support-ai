# Production Deployment Guide - Magic Link Authentication

## Quick Start (5 minutes)

### For Development (Test locally)
```bash
# 1. No configuration needed!
# 2. Emails will be mocked (logged to console)
# 3. Start server:
python -m uvicorn main:app --host 0.0.0.0 --port 8001

# 4. Test magic link request:
curl -X POST http://localhost:8001/api/auth/magic-link/request \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com"}'

# 5. Check logs for [MOCK EMAIL] with verification link
```

### For Production (Deploy to cloud)

#### Step 1: Get Mailgun Account (2 minutes)
1. Go to https://mailgun.com
2. Click "Sign up"
3. Create free account (100 emails/day included)
4. Verify your email
5. Create/verify a domain (can use free sandbox)
6. Copy API Key from dashboard
7. Copy Domain from dashboard

#### Step 2: Deploy to Render (5 minutes)
1. Go to https://render.com
2. Connect your GitHub account
3. New → Web Service
4. Select this repository
5. Set environment variables:
   ```
   DATABASE_URL=postgresql+psycopg2://...  # Your Supabase URL
   BASE_URL=https://your-app.onrender.com
   MAILGUN_API_KEY=key-abc123xyz          # From Mailgun
   MAILGUN_DOMAIN=mg.yourdomain.com       # From Mailgun
   AUTH_SECRET_KEY=super-secret-random-key
   ```
6. Deploy
7. Test: `https://your-app.onrender.com/health`

#### Step 3: Test Magic Link (2 minutes)
```bash
# Request link
curl -X POST https://your-app.onrender.com/api/auth/magic-link/request \
  -H "Content-Type: application/json" \
  -d '{"email":"your-email@gmail.com"}'

# Check your email for link
# Click link or:
curl "https://your-app.onrender.com/api/auth/magic-link/verify?token=XXXXX&email=your-email@gmail.com"

# You get back:
# {
#   "access_token": "eyJhbGc...",
#   "token_type": "bearer",
#   "role": "agent",
#   "email": "your-email@gmail.com"
# }
```

---

## Detailed Deployment Instructions

### Platform: Render.com (Recommended)

#### Prerequisites
- GitHub account with this repository
- Mailgun account with API key
- Supabase database URL

#### Deployment Steps

1. **Connect GitHub**
   - Go to https://render.com
   - Sign up or log in
   - Click "New" → "Web Service"
   - Select repository
   - Name: `support-portal`
   - Environment: `Python`
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn main:app --host 0.0.0.0 --port 8080`

2. **Set Environment Variables**
   ```
   DATABASE_URL=postgresql+psycopg2://user:pass@host/db
   BASE_URL=https://support-portal.onrender.com
   MAILGUN_API_KEY=key-123456789abcdef
   MAILGUN_DOMAIN=mg.your-domain.com
   AUTH_SECRET_KEY=generate-random-key-with-32-chars
   LOG_LEVEL=INFO
   WORKERS=2
   ```

3. **Deploy**
   - Click "Create Web Service"
   - Wait for deployment (2-3 minutes)
   - Check "Logs" tab for errors

4. **Verify Deployment**
   ```bash
   curl https://support-portal.onrender.com/health
   # Should return: {"status":"ok"}
   ```

---

### Platform: Heroku

#### Prerequisites
- GitHub account
- Heroku account (free tier available)
- Mailgun account

#### Steps

1. **Create Heroku App**
   ```bash
   heroku create support-portal
   ```

2. **Set Config Variables**
   ```bash
   heroku config:set DATABASE_URL="postgresql+psycopg2://..."
   heroku config:set BASE_URL="https://support-portal.herokuapp.com"
   heroku config:set MAILGUN_API_KEY="key-abc123"
   heroku config:set MAILGUN_DOMAIN="mg.yourdomain.com"
   heroku config:set AUTH_SECRET_KEY="your-random-secret-key"
   ```

3. **Deploy**
   ```bash
   git push heroku main
   ```

4. **Check Logs**
   ```bash
   heroku logs --tail
   ```

---

### Platform: Azure App Service

#### Prerequisites
- Microsoft Azure account
- Mailgun account

#### Steps

1. **Create App Service**
   - Azure Portal
   - Create resource → App Service
   - Python 3.11
   - Linux
   - Region: Choose closest

2. **Configure Application Settings**
   - Go to Configuration
   - New application settings:
     ```
     DATABASE_URL = postgresql+psycopg2://...
     BASE_URL = https://your-app.azurewebsites.net
     MAILGUN_API_KEY = key-xxx
     MAILGUN_DOMAIN = mg.xxx
     AUTH_SECRET_KEY = random-key
     ```

3. **Deploy Code**
   - Option A: Git deployment
   - Option B: FTP upload
   - Option C: Azure DevOps

---

### Platform: AWS Elastic Beanstalk

#### Steps

1. **Create `.ebextensions/python.config`**
   ```yaml
   option_settings:
     aws:elasticbeanstalk:application:environment:
       PYTHONPATH: /var/app/current:$PYTHONPATH
   ```

2. **Deploy**
   ```bash
   eb create support-portal
   eb setenv DATABASE_URL="..."
   eb deploy
   ```

---

### Platform: DigitalOcean App Platform

1. Go to https://cloud.digitalocean.com/apps
2. Create App
3. Connect GitHub
4. Select Dockerfile or Python
5. Set environment variables
6. Deploy

---

## Mailgun Setup Guide

### Get Free Account

1. **Sign Up**
   - https://mailgun.com
   - Click "Sign Up"
   - Create free account

2. **Create Domain**
   - Dashboard → Sending → Domains
   - Add domain or use sandbox: `sandbox-xxxxx.mailgun.org`
   - Verify domain (if custom domain)

3. **Get API Key**
   - Dashboard → API → Private API Key
   - Copy the key starting with `key-`

4. **Copy Domain**
   - Dashboard → Sending → Domains
   - Copy domain name: `mg.yourdomain.com` or sandbox

5. **Update .env**
   ```env
   MAILGUN_API_KEY=key-1234567890abcdef
   MAILGUN_DOMAIN=mg.yourdomain.com
   ```

6. **Verify Email (Sandbox Only)**
   - If using sandbox domain, add recipient emails
   - Dashboard → Domains → Authorized Recipients
   - Add email addresses that can receive emails
   - Verify via email link

---

## Testing Production Deployment

### 1. Health Check
```bash
curl https://your-app.com/health
# Expected: {"status":"ok"}
```

### 2. Magic Link Request
```bash
curl -X POST https://your-app.com/api/auth/magic-link/request \
  -H "Content-Type: application/json" \
  -d '{"email":"test@gmail.com"}'

# Expected: 
# {
#   "status": "success",
#   "message": "Check your email..."
# }
```

### 3. Check Email
- Wait 10-30 seconds for email
- Check inbox and spam folder
- Verify link format: `https://your-app.com/api/auth/magic-link/verify?token=...&email=...`

### 4. Click Magic Link
- Click link in email
- Or manually visit: `https://your-app.com/api/auth/magic-link/verify?token=TOKEN&email=EMAIL`
- Should receive JWT token

### 5. Use JWT Token
```bash
curl https://your-app.com/api/chat/list \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Should work and return data
```

---

## Configuration Reference

### Required Environment Variables
```env
# Database (from Supabase)
DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/db

# Application
BASE_URL=https://your-app-name.onrender.com
AUTH_SECRET_KEY=your-secret-key-at-least-32-chars

# Email (from Mailgun)
MAILGUN_API_KEY=key-abc123def456
MAILGUN_DOMAIN=mg.yourdomain.com

# Optional
LOG_LEVEL=INFO              # DEBUG, INFO, WARNING, ERROR
WORKERS=2                   # Number of Uvicorn workers
```

### Optional Environment Variables
```env
# Authentication
REFRESH_TOKEN_EXPIRE_DAYS=7
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Features
RAG_ENABLED=true
VECTOR_STORE_ENABLED=false
WEBSOCKET_ENABLED=true

# API Limits
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=100
```

---

## Troubleshooting

### Emails Not Being Sent

**Problem**: Magic link requested but no email received

**Solution**:
1. Check Mailgun API key is correct
   ```bash
   echo $MAILGUN_API_KEY
   # Should be: key-xxxxxxxxxxxxxxxx
   ```

2. Check domain is correct
   ```bash
   echo $MAILGUN_DOMAIN
   # Should be: mg.yourdomain.com or sandbox-xxxxx.mailgun.org
   ```

3. If using sandbox, verify recipient email
   - Mailgun Dashboard → Domains → Authorized Recipients
   - Add your test email address
   - Verify via email confirmation

4. Check logs for errors
   - Render: Logs tab
   - Heroku: `heroku logs --tail`
   - Azure: Application Insights

5. Check Mailgun dashboard for events
   - Mailgun Dashboard → Logs
   - Look for rejected/failed messages

### Server Won't Start

**Problem**: `Aborted!` or won't start

**Solution**:
1. Check logs for errors
2. Verify DATABASE_URL is correct
3. Ensure all required env vars are set
4. Check Python version (3.10+)
5. Check memory/CPU limits

### Link Expired Too Quickly

**Problem**: Link says "expired" when clicked

**Solution**:
1. Check server time is correct
2. Verify timezone settings
3. Check TOKEN_EXPIRE_MINUTES (default: 15)
4. Increase if needed

### User Can't Log In

**Problem**: Link works but login fails

**Solution**:
1. Check JWT token is returned
2. Verify token in Authorization header
3. Check database for user creation
4. Review access logs

---

## Monitoring in Production

### Check Application Health
```bash
# Daily
curl https://your-app.com/health

# Or use monitoring service:
# - Uptime Robot (uptime-robot.com)
# - Monitoring (datadog, newrelic, etc.)
```

### Monitor Email Delivery
- Mailgun Dashboard → Logs
- Filter by date range
- Check for:
  - Delivered ✓
  - Failed ✗
  - Bounced ✗
  - Rejected ✗

### Check Application Logs
- Render: Logs tab
- Heroku: `heroku logs --tail`
- Azure: Application Insights
- CloudWatch (if AWS)

### Set Up Alerts
- CPU usage > 80%
- Memory usage > 90%
- Error rate > 5%
- Response time > 2s
- Downtime

---

## Scaling for Production

### Increase Capacity

**Render.com**:
- Settings → Plan → Upgrade
- Choose instance size

**Heroku**:
```bash
heroku dyno:resize standard-1x
```

**Azure**:
- Scale up → Plan
- Choose higher tier

### Add Database Replicas

For high traffic:
1. Supabase: Enable Read Replicas
2. Connection pooling: Enable Supabase PgBouncer
3. Cache layer: Add Redis

### Load Balancing

For multiple instances:
1. Deploy multiple instances
2. Use platform's load balancer
3. Configure health checks
4. Monitor each instance

---

## Security Checklist

- [ ] DATABASE_URL uses strong password
- [ ] AUTH_SECRET_KEY is random (32+ chars)
- [ ] MAILGUN_API_KEY is kept secret (never in git)
- [ ] BASE_URL uses HTTPS
- [ ] All environment variables are set
- [ ] No debug mode in production
- [ ] Rate limiting enabled
- [ ] CORS properly configured
- [ ] Database backups enabled
- [ ] SSL/TLS certificate valid

---

## Maintenance

### Regular Backups
- Supabase: Automatic daily backups
- Render: Manual backups available
- Azure: Enable backup

### Database Cleanup
```bash
# Remove expired magic links (optional)
# Run this monthly via cron job:
python scripts/db_cleanup.py
```

### Update Dependencies
```bash
# Monthly security updates
pip install --upgrade -r requirements.txt
```

### Monitor Logs
- Check for errors daily
- Review Mailgun bounce rates
- Monitor API usage

---

## Support

For issues:
1. Check logs (specific platform instructions above)
2. Test locally first with mock emails
3. Verify all environment variables are set
4. Check Mailgun account status
5. Review this guide's troubleshooting section

---

## Next Steps

1. ✅ Choose hosting platform (Render recommended)
2. ✅ Get Mailgun account and credentials
3. ✅ Deploy application
4. ✅ Set environment variables
5. ✅ Test magic link flow
6. ✅ Monitor logs
7. ✅ Set up backups
8. ✅ Configure alerts

**Estimated time: 15 minutes**

**Ready to go live! 🚀**
