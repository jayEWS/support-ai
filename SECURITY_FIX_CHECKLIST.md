# 🚨 CRITICAL SECURITY CHECKLIST - FIX BEFORE PRODUCTION

## P0 CRITICAL (Must fix immediately - 1 week)

- [ ] **SQL Injection** - Remove arbitrary SQL or whitelist only
  - File: `app/routes/ai_tools.py`
  - Status: 🔴 CRITICAL
  - Fix time: 1 day
  
- [ ] **Prompt Injection Detection** - Implement semantic guardrails
  - File: `app/services/guardrail_service.py`
  - Status: 🔴 CRITICAL
  - Fix time: 1 day

- [ ] **Magic Link Rate Limit** - Add rate limiting on verify endpoint
  - File: `main.py` line ~846
  - Status: 🔴 CRITICAL
  - Fix time: 15 min

- [ ] **Race Condition (Vouchers)** - Database-level locking
  - File: `app/routes/ai_tools.py`
  - Status: 🔴 CRITICAL
  - Fix time: 1 day

- [ ] **JWT Role Tampering** - Implement proper RBAC model
  - File: `app/core/auth_deps.py`, `main.py`
  - Status: 🔴 CRITICAL
  - Fix time: 2-3 days

- [ ] **Cross-Tenant IDOR** - Add ticket ownership validation
  - File: `app/routes/ticket_routes.py`
  - Status: 🔴 CRITICAL
  - Fix time: 1-2 days

- [ ] **WhatsApp Webhook Bypass** - Enforce strict signature validation
  - File: `app/webhook/whatsapp.py`
  - Status: 🔴 CRITICAL
  - Fix time: 1 day

- [ ] **RAG Data Poisoning** - Validate KB content before indexing
  - File: `app/services/rag_service.py`
  - Status: 🔴 CRITICAL
  - Fix time: 1 day

---

## P1 HIGH (Fix within 1-2 weeks)

- [ ] **Weak RBAC** - Implement granular permissions
  - File: `app/core/auth_deps.py`
  - Status: 🟠 HIGH
  
- [ ] **Missing CSRF Tokens** - Add X-CSRF-Token validation
  - File: `app/core/middleware.py`
  - Status: 🟠 HIGH
  
- [ ] **Weak Logout** - Revoke access tokens immediately
  - File: `main.py` line ~591
  - Status: 🟠 HIGH
  
- [ ] **Secrets in Error Messages** - Mask exceptions
  - File: `app/core/logging.py`
  - Status: 🟠 HIGH
  
- [ ] **Hardcoded Secrets** - Move to config
  - File: `app/core/config.py`
  - Status: 🟠 HIGH
  
- [ ] **CORS Wildcard Allowed** - Require explicit origins
  - File: `main.py` line 384
  - Status: 🟠 HIGH
  
- [ ] **Environment Validation** - Require critical vars
  - File: `main.py` line 46
  - Status: 🟠 HIGH

---

## P2 MEDIUM (Fix within 1 month)

- [ ] **N+1 Query Problem** - Use joinedload for relationships
  - File: `app/routes/system_routes.py`
  - Status: 🟡 MEDIUM
  
- [ ] **PII in Logs** - Mask sensitive fields
  - File: Multiple logging calls
  - Status: 🟡 MEDIUM
  
- [ ] **File Upload Validation** - Use MIME type checking
  - File: `app/routes/knowledge_routes.py`
  - Status: 🟡 MEDIUM
  
- [ ] **Storage Quota** - Implement per-user limits
  - File: `app/routes/portal_routes.py`
  - Status: 🟡 MEDIUM
  
- [ ] **Missing Indexes** - Add database indexes
  - File: `app/models/models.py`
  - Status: 🟡 MEDIUM

---

## VERIFICATION CHECKLIST

### Before Going to Production, Verify:

- [ ] All P0 issues fixed and tested
- [ ] All P1 issues fixed and tested
- [ ] SAST scan passed (no vulnerabilities)
- [ ] Rate limiting working on all public endpoints
- [ ] Database backups configured and tested
- [ ] Monitoring/alerting configured
- [ ] SSL/TLS certificate valid and renewed
- [ ] Secrets not in git history
  ```bash
  git log --all --full-history -- ".env"
  git log --all --full-history | grep -i "password\|secret\|key"
  ```
- [ ] No debug mode in production
  ```python
  assert not settings.DEBUG, "DEBUG must be False"
  ```
- [ ] Auth secrets are strong (32+ bytes)
  ```bash
  openssl rand -hex 32
  ```

---

## SECURITY SCANNING COMMANDS

```bash
# 1. Check for secrets in code
pip install detect-secrets
detect-secrets scan > .secrets.baseline
detect-secrets audit .secrets.baseline

# 2. Check Python vulnerabilities
pip install safety
safety check -r requirements.txt

# 3. Code quality & security
pip install bandit
bandit -r app/ -f json -o bandit-report.json

# 4. Dependency audit
pip install pip-audit
pip-audit

# 5. Git secret scanning
pip install git-leaks
git-leaks detect --verbose
```

---

## MONITORING ALERTS TO SET UP

- [ ] Multiple failed login attempts (>5 in 5 min)
- [ ] Admin role assignment
- [ ] SQL query tool usage
- [ ] Database connection failures
- [ ] API error rate >5%
- [ ] Unusual voucher redemption rate
- [ ] WhatsApp webhook failures
- [ ] Unauthorized access attempts (403 errors)

---

## TIMELINE

- **Week 1:** Fix all P0 (Critical) issues
- **Week 2:** Fix all P1 (High) issues
- **Week 3:** Security testing and verification
- **Week 4:** Fix P2 issues and final audit

**Total:** ~1 month before production-ready

---

## RED FLAGS - NEVER GO LIVE WITH:

🛑 NEVER DEPLOY IF:
- [ ] DEBUG mode is enabled
- [ ] CORS allows "*"
- [ ] AUTH_SECRET_KEY is empty
- [ ] Database credentials in code
- [ ] No rate limiting on public endpoints
- [ ] SQL injection vector exists
- [ ] Magic link brute force possible
- [ ] JWT role tampering possible
- [ ] Arbitrary SQL execution allowed
- [ ] Ticket IDOR vulnerability exists

---

**Last Updated:** March 17, 2026  
**Status:** 🔴 NOT PRODUCTION READY  
**Estimated Fix Time:** 4 weeks (full time)  
**Recommended:** Engage security firm for penetration testing after fixes

