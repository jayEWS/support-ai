import uuid
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.logging import logger, trace_id_var

class CustomCSRFMiddleware(BaseHTTPMiddleware):
    """
    Simpler CSRF protection for APIs:
    Requires a custom header (X-Requested-With or X-CSRF-Token) for state-changing requests.
    This works because browsers do not allow custom headers to be sent cross-domain without preflight (CORS).
    """
    async def dispatch(self, request: Request, call_next):
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            # Check if request is authenticated via cookie
            has_auth_cookie = "access_token" in request.cookies
            
            # If authenticated via cookie, we MUST have a custom header to prevent CSRF
            if has_auth_cookie:
                csrf_token = request.headers.get("X-CSRF-Token")
                requested_with = request.headers.get("X-Requested-With")
                
                if not csrf_token and not requested_with:
                    logger.warning(f"[SECURITY] Possible CSRF attempt blocked: {request.url}")
                    raise HTTPException(
                        status_code=403, 
                        detail="CSRF validation failed. Custom header (X-CSRF-Token or X-Requested-With) missing."
                    )
                    
        response = await call_next(request)
        return response

class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """
    Ensures every request has a unique trace ID for logging and observability.
    """
    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())
        
        # Set trace ID in contextvar for logs
        token = trace_id_var.set(trace_id)
        
        try:
            response = await call_next(request)
            # Tag response with same ID for debugging
            response.headers["X-Trace-ID"] = trace_id
            return response
        finally:
            trace_id_var.reset(token)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Sets security headers for production safety (HSTS, CSP, No-Sniff).
    """
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # 1. HSTS (Strict Transport Security) - Ensure HTTPS
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # 2. X-Content-Type-Options - Prevent MIME-type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # 3. X-Frame-Options - Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # 4. X-XSS-Protection
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # 5. Referrer-Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # 6. Basic CSP (Adjust for frontend needs)
        # Allows self, Google Fonts, and Meta Assets
        if not response.headers.get("Content-Security-Policy"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://connect.facebook.net https://cdn.tailwindcss.com; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.tailwindcss.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data: https://*.googleusercontent.com https://*.fbcdn.net; "
                "connect-src 'self' wss: https://*.vertexai.goog https://*.googleapis.com;"
            )
            
        return response
