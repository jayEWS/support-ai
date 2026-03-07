import multiprocessing
import os

# Gunicorn Production Configuration

# Bind to 0.0.0.0 to allow external access (e.g., from Nginx/Load Balancer)
bind = "0.0.0.0:8001"

# Workers: Reduced to 1 for small VM stability (prevents RAM freeze)
workers = 1
worker_class = "uvicorn.workers.UvicornWorker"

# Threads: 2 is enough for small instances
threads = 2

# Timeout: Increase for long-running AI tasks (e.g., RAG + LLM generation)
timeout = 120
keepalive = 5

# Logging
accesslog = "-"  # Stdout
errorlog = "-"   # Stderr
loglevel = "info"

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Resilience
preload_app = True  # Load app before forking workers (saves memory)
max_requests = 1000 # Restart worker after 1000 requests (prevents memory leaks)
max_requests_jitter = 50 # Add jitter to prevent all workers restarting at once

def on_starting(server):
    print("🚀 Gunicorn is starting Edgeworks Support Portal...")
