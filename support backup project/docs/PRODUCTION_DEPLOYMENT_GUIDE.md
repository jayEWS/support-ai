# 🚀 Production Deployment Guide - Support Portal Edgeworks

**Target:** Support Portal Edgeworks v2.1  
**Deployment Platforms:** Render, AWS, Azure, Google Cloud, or Self-Hosted  
**Last Updated:** February 28, 2026

---

## 📋 Quick Start (5 Steps)

```bash
# 1. Clone and setup
git clone <repo-url>
cd support-portal-edgeworks
cp .env.example .env
# Edit .env with production credentials

# 2. Build Docker image
docker build -t support-portal-edgeworks:latest .

# 3. Test locally
docker run -p 8000:8000 --env-file .env support-portal-edgeworks

# 4. Verify endpoints
curl http://localhost:8000/health

# 5. Deploy to production platform (see platform-specific guides below)
```

---

## 🔐 Security Requirements Checklist

Before deployment, ensure:

- ✅ **No hardcoded secrets** (all use environment variables)
- ✅ **HTTPS enabled** (SSL/TLS certificates configured)
- ✅ **CORS properly restricted** (not `["*"]` in production)
- ✅ **Strong auth secrets** (min 32 chars, random)
- ✅ **MFA enabled** (`MFA_ENABLED=true`, `MFA_DEV_RETURN_CODE=false`)
- ✅ **Database encrypted** (SQL Server with `Encrypt=yes`)
- ✅ **Cookies secure** (`COOKIE_SECURE=true`, `COOKIE_SAMESITE=strict`)
- ✅ **API keys rotated** (if reusing from development)
- ✅ **Secrets not in git history** (scan with `git-secret` or similar)
- ✅ **Database backups** automated daily

---

## 🌍 Platform-Specific Deployment Guides

### 1. Render (Recommended for Free Tier)

**Advantages:** Free tier available, automatic HTTPS, easy deployment  
**Memory:** 512MB (free tier suitable for dev/demo)

#### Steps:

1. **Push to GitHub:**
   ```bash
   git push origin main
   ```

2. **Create render.yaml** (already included):
   - Review `render.yaml` configuration
   - Adjust resource allocation if needed

3. **Deploy via Render Dashboard:**
   - Go to [render.com](https://render.com)
   - Click "New" → "Web Service"
   - Connect your GitHub repository
   - Render will auto-detect `render.yaml`
   - Click "Deploy"

4. **Set Environment Variables:**
   ```
   OPENAI_API_KEY = sk-...
   API_SECRET_KEY = (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
   AUTH_SECRET_KEY = (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
   DATABASE_URL = mssql+pyodbc://user:pass@azure-host:1433/db?driver=...
   COOKIE_SECURE = true
   COOKIE_SAMESITE = strict
   ALLOWED_ORIGINS = https://yourdomain.render.app
   MFA_DEV_RETURN_CODE = false
   ```

5. **Verify Deployment:**
   ```bash
   curl https://your-service.render.app/health
   ```

**Render Dashboard:** https://dashboard.render.com

---

### 2. AWS (Elastic Container Service)

**Advantages:** Scalable, production-grade, enterprise support  
**Minimum Cost:** ~$50/month

#### Steps:

1. **Create ECR Repository:**
   ```bash
   aws ecr create-repository --repository-name support-portal-edgeworks
   ```

2. **Build and Push Image:**
   ```bash
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
   docker build -t support-portal-edgeworks:latest .
   docker tag support-portal-edgeworks:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/support-portal-edgeworks:latest
   docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/support-portal-edgeworks:latest
   ```

3. **Create ECS Task Definition:**
   ```json
   {
     "family": "support-portal-edgeworks",
     "containerDefinitions": [
       {
         "name": "app",
         "image": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/support-portal-edgeworks:latest",
         "portMappings": [{"containerPort": 8000}],
         "environment": [
           {"name": "OPENAI_API_KEY", "value": "sk-..."},
           {"name": "API_SECRET_KEY", "value": "..."},
           {"name": "AUTH_SECRET_KEY", "value": "..."}
         ]
       }
     ]
   }
   ```

4. **Create ECS Cluster & Service:**
   - Use AWS Console or CloudFormation
   - Configure load balancer (ALB)
   - Set auto-scaling (min 1, max 5)

5. **Configure RDS for SQL Server:**
   - Create RDS SQL Server instance
   - Configure security groups (allow port 1433)
   - Update `DATABASE_URL` env var

---

### 3. Azure Container Instances / App Service

**Advantages:** Microsoft ecosystem, strong enterprise support  
**Minimum Cost:** ~$30/month

#### Steps:

1. **Create Azure Container Registry:**
   ```bash
   az acr create --resource-group myRG --name myregistry --sku Basic
   az acr build --registry myregistry --image support-portal-edgeworks:latest .
   ```

2. **Deploy to App Service:**
   ```bash
   az appservice plan create --name myplan --resource-group myRG --sku B1 --is-linux
   az webapp create --resource-group myRG --plan myplan --name support-portal --deployment-container-image-name myregistry.azurecr.io/support-portal-edgeworks:latest
   ```

3. **Set Environment Variables:**
   ```bash
   az webapp config appsettings set --resource-group myRG --name support-portal --settings OPENAI_API_KEY=sk-... API_SECRET_KEY=...
   ```

4. **Create Azure SQL Database:**
   - Create SQL Server instance
   - Create database
   - Update `DATABASE_URL` connection string

---

### 4. Google Cloud Run

**Advantages:** Serverless, pay-per-use, quick deployment  
**Pricing:** Free tier available (2M requests/month)

#### Steps:

1. **Build and Push to Artifact Registry:**
   ```bash
   gcloud auth configure-docker us-central1-docker.pkg.dev
   docker build -t us-central1-docker.pkg.dev/PROJECT_ID/support-portal/app:latest .
   docker push us-central1-docker.pkg.dev/PROJECT_ID/support-portal/app:latest
   ```

2. **Deploy to Cloud Run:**
   ```bash
   gcloud run deploy support-portal \
     --image us-central1-docker.pkg.dev/PROJECT_ID/support-portal/app:latest \
     --platform managed \
     --region us-central1 \
     --memory 512Mi \
     --timeout 120 \
     --set-env-vars OPENAI_API_KEY=sk-...,API_SECRET_KEY=...
   ```

3. **Create Cloud SQL for SQL Server:**
   - Use Azure SQL (Cloud SQL doesn't support SQL Server natively)
   - Or use Compute Engine with self-hosted SQL Server

---

### 5. Self-Hosted (Docker Compose)

**Advantages:** Full control, no vendor lock-in  
**Minimum Requirements:** 2GB RAM, 10GB disk, Linux server

#### Steps:

1. **Prepare Server:**
   ```bash
   ssh user@your-server.com
   cd /opt
   git clone <repo> support-portal-edgeworks
   cd support-portal-edgeworks
   ```

2. **Configure Environment:**
   ```bash
   cp .env.example .env
   nano .env  # Edit with production credentials
   ```

3. **Set Up SQL Server (if not remote):**
   ```bash
   docker run -e "ACCEPT_EULA=Y" -e "SA_PASSWORD=YourPassword123!" -p 1433:1433 -d mcr.microsoft.com/mssql/server:2022-latest
   ```

4. **Deploy with Docker Compose:**
   ```bash
   docker-compose up -d
   docker-compose logs -f
   ```

5. **Set Up Nginx Reverse Proxy:**
   ```bash
   sudo apt-get install nginx
   sudo nano /etc/nginx/sites-available/default
   ```
   
   ```nginx
   server {
       listen 80;
       server_name yourdomain.com;

       location / {
           proxy_pass http://localhost:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
           
           # WebSocket support
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
       }
   }
   ```

6. **Enable HTTPS (Let's Encrypt):**
   ```bash
   sudo apt-get install certbot python3-certbot-nginx
   sudo certbot --nginx -d yourdomain.com
   ```

7. **Restart Services:**
   ```bash
   sudo systemctl restart nginx
   docker-compose restart
   ```

---

## 📊 Performance Tuning

### Database Optimization
```python
# SQL Server connection pooling (already configured)
# pool_size=10, max_overflow=20
# Adjust based on expected concurrent users
```

### Gunicorn Workers
Current setting: **1 worker** (free tier)  
For production, scale based on CPU cores:
```bash
# In Dockerfile
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", ...]
# For 2-4 cores: 2-4 workers
# For 4+ cores: 4-8 workers
```

### Caching Strategy
- Enable Redis caching for RAG queries
- Cache frequently accessed knowledge base documents
- Configure TTL based on update frequency

### Database Indexes
```sql
-- Add indexes for common queries
CREATE INDEX idx_tickets_status ON tickets(status);
CREATE INDEX idx_messages_session ON chat_messages(chat_session_id);
CREATE INDEX idx_messages_created ON chat_messages(created_at);
```

---

## 🔄 Monitoring & Logging

### Essential Metrics to Monitor
1. **Application Health:**
   - CPU usage
   - Memory usage
   - Uptime/availability
   - Error rate

2. **API Metrics:**
   - Request latency (p50, p95, p99)
   - Request volume
   - Error rate by endpoint
   - 5xx error rate

3. **Database Metrics:**
   - Connection pool usage
   - Query latency
   - Index usage
   - Slow query log

4. **Business Metrics:**
   - Active chats
   - MFA success rate
   - Average response time
   - Customer satisfaction (CSAT)

### Logging Setup
```bash
# ELK Stack (Elasticsearch, Logstash, Kibana)
# or CloudWatch, DataDog, Splunk, etc.
```

### Health Check Endpoint
```bash
curl https://yourdomain.com/health
```

---

## 🆘 Troubleshooting

### Application won't start
```bash
docker logs <container-id>
# Check for: Missing env vars, database connection, FAISS index errors
```

### High memory usage
```bash
# Reduce vector database size or enable pagination
# Check for memory leaks in WebSocket connections
```

### Slow API responses
```bash
# Enable database query logging
# Add Redis caching
# Optimize RAG search parameters
```

### Database connection errors
```bash
# Verify DATABASE_URL format
# Test connection: python scripts/check_db.py
# Check SQL Server firewall rules
```

---

## 🔒 Production Security Hardening

### Additional Security Measures
1. **Rate Limiting:**
   ```python
   # Add to main.py
   from slowapi import Limiter
   limiter = Limiter(key_func=get_remote_address)
   @app.get("/api/chat", dependencies=[Depends(limiter.limit("10/minute"))])
   ```

2. **WAF (Web Application Firewall):**
   - Enable on cloud provider (AWS WAF, Azure WAF)
   - Block common attack patterns

3. **DDoS Protection:**
   - Enable on CDN (CloudFlare, Akamai)
   - Set rate limits

4. **API Authentication:**
   - Rotate API keys regularly
   - Use short-lived tokens
   - Implement API versioning

5. **Secrets Management:**
   - Use AWS Secrets Manager / Azure Key Vault
   - Never hardcode secrets
   - Rotate credentials quarterly

---

## 📈 Scaling Strategy

### Horizontal Scaling
1. **Stateless API Design:** ✅ Ready
2. **Load Balancer:** Configure ALB/NLB
3. **Auto Scaling Group:** Min 2, Max 10 instances
4. **Shared Database:** Use managed SQL Server

### Vertical Scaling
- Increase container memory/CPU
- Increase database resources
- Enable read replicas for database

---

## 🎯 Deployment Validation Checklist

After deployment, verify:

- [ ] Health endpoint returns 200 OK
- [ ] Can create user and authenticate
- [ ] MFA works correctly
- [ ] WebSocket chat connects
- [ ] RAG engine retrieves documents
- [ ] Emails send correctly
- [ ] WhatsApp integration works (if enabled)
- [ ] Database backups are running
- [ ] Logs are being collected
- [ ] Monitoring is active

---

## 📞 Support & Resources

- **Documentation:** See README.md, CHAT_API.md
- **Issues:** Check GitHub issues or local logs
- **Emergency:** Contact DevOps team
- **Escalation:** Contact Architecture team

---

**Deployment Date:** _________  
**Deployed By:** _________  
**Version:** _________  
**Environment:** [STAGING / PRODUCTION]
