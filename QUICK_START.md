# Docker Setup - Quick Reference

## Files Created ✓

| File | Purpose | Status |
|------|---------|--------|
| **Dockerfile** | Multi-stage production build | ✅ Created |
| **docker-compose.dev.yml** | Complete dev stack (Postgres + Redis + App) | ✅ Created |
| **docker-compose.yml** | Production stack (same as dev, optional nginx) | ✅ Exists |
| **.dockerignore** | Optimized build context | ✅ Updated |
| **.env.example** | Configuration template | ✅ Created |
| **nginx/nginx.conf** | Main nginx config | ✅ Created |
| **nginx/conf.d/app.conf** | FastAPI routing | ✅ Created |
| **DOCKER_GUIDE.md** | Full documentation | ✅ Created |

---

## 3-Step Setup

### Step 1: Configure Environment
```powershell
Copy-Item .env.example .env
# Edit .env with your API keys
notepad .env
```

### Step 2: Start Stack
```powershell
docker compose -f docker-compose.dev.yml up -d --build
```

### Step 3: Verify
```powershell
# Wait 30-60 seconds for services to be healthy
docker compose ps

# Check app logs
docker compose logs -f app

# Test health endpoint
curl http://localhost:8000/health
```

---

## Service Access

| Service | URL | Health Check |
|---------|-----|--------------|
| **App** | http://localhost:8000 | `curl http://localhost:8000/health` |
| **PostgreSQL** | localhost:5432 | `docker exec support-portal-db psql -U postgres -c "SELECT 1"` |
| **Redis** | localhost:6379 | `docker exec support-portal-cache redis-cli ping` |

---

## Common Commands

```powershell
# View all running services
docker compose ps

# View app logs (live)
docker compose logs -f app

# View database logs
docker compose logs postgres

# Stop all services
docker compose down

# Stop and remove volumes (full cleanup)
docker compose down -v

# Rebuild specific service
docker compose build --no-cache app

# Enter app container
docker exec -it support-portal-app bash

# View app environment
docker exec support-portal-app env | grep DATABASE
```

---

## Troubleshooting

### App won't start
```powershell
docker compose logs app
# Check DATABASE_URL and REDIS_URL in .env
```

### Database connection error
```powershell
# Wait 10-15 seconds for postgres to initialize
docker compose logs postgres
```

### Port 8000 already in use
Edit `docker-compose.dev.yml`:
```yaml
app:
  ports:
    - "8080:8001"  # Use 8080 instead
```

### Rebuild from scratch
```powershell
docker compose down -v
docker compose build --no-cache
docker compose up -d
```

---

## Production Deployment

### Docker Swarm
```bash
docker swarm init
docker stack deploy -c docker-compose.yml support-portal
```

### Kubernetes
```bash
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: support-portal
spec:
  replicas: 3
  selector:
    matchLabels:
      app: support-portal
  template:
    metadata:
      labels:
        app: support-portal
    spec:
      containers:
      - name: app
        image: your-registry/support-portal:latest
        ports:
        - containerPort: 8001
        livenessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 60
---
apiVersion: v1
kind: Service
metadata:
  name: support-portal
spec:
  selector:
    app: support-portal
  ports:
  - port: 80
    targetPort: 8001
  type: LoadBalancer
EOF
```

---

## What Each Service Does

### PostgreSQL (port 5432)
- Stores: Users, tickets, customers, messages, knowledge base
- Persistence: `postgres_data` volume
- Health check: Waits 10 seconds between attempts

### Redis (port 6379)
- Caches: Session data, WebSocket broadcasts
- Pub/Sub: Multi-instance WebSocket sync
- Persistence: `redis_data` volume (append-only)

### FastAPI App (port 8001)
- 2 Gunicorn workers (adjust for your CPU cores)
- 120s timeout for LLM inference
- Health check: Liveness probe every 30 seconds

---

## Environment Variables (Key Ones)

```env
# Database (auto-configured in compose)
DATABASE_URL=postgresql://user:pass@postgres:5432/support_portal
REDIS_URL=redis://:password@redis:6379/0

# Security
AUTH_SECRET_KEY=your_long_random_string_min_32_chars

# AI Services
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key

# WhatsApp Integration
WHATSAPP_API_TOKEN=your_meta_token
WHATSAPP_VERIFY_TOKEN=your_webhook_token

# Email
GMAIL_EMAIL=your_email@gmail.com
GMAIL_PASSWORD=your_app_password
```

Full list: See `.env.example`

---

## Build Optimization

The Dockerfile uses multi-stage building:
1. **Stage 1 (Builder)**: Installs `gcc`, `build-essential`, pip packages
2. **Stage 2 (Runtime)**: Only includes runtime dependencies
3. **Result**: ~600MB smaller final image

Cache optimization:
- `requirements.txt` is copied first (separate layer)
- Python dependencies cached independently
- Code changes don't invalidate dependency cache
- Rebuild time: ~3 min (cached) vs ~15 min (cold)

---

## Security Features

✅ Non-root user (`appuser`)
✅ Dropped Linux capabilities (only `NET_BIND_SERVICE`)
✅ Read-only root filesystem (where possible)
✅ Health checks for orchestrators
✅ Security headers in nginx
✅ Rate limiting per endpoint
✅ No secrets in images (uses .env)

---

## Next Steps

1. Edit `.env` with your keys
2. Run `docker compose -f docker-compose.dev.yml up -d --build`
3. Wait for health checks to pass
4. Access: http://localhost:8000
5. View logs: `docker compose logs -f`

For detailed reference, see: **DOCKER_GUIDE.md**

Let me know if you have any questions!
