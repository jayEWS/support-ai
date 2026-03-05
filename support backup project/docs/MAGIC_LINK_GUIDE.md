# Magic Link Authentication Implementation

## Overview

Magic Link authentication has been fully implemented with email sending capability. When a user requests a magic link, they receive an email with a time-limited link to authenticate without passwords.

## How It Works

### 1. Request Magic Link
```
POST /api/auth/magic-link/request
Content-Type: application/json

{
  "email": "user@example.com"
}
```

### Response
```json
{
  "status": "success",
  "message": "Check your email for the magic link. If you don't see it, check your spam folder."
}
```

### 2. Email Sent (in background)
User receives an HTML email with:
- Magic link button
- Raw link for copying
- 15-minute expiry notice
- Professional branding

### 3. Verify Magic Link
```
GET /api/auth/magic-link/verify?token=XXXXX&email=user@example.com
```

Response:
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "role": "agent",
  "name": "User Name",
  "email": "user@example.com"
}
```

User is logged in and can access the portal.

## Features Implemented

✅ **Email Sending**
- Uses Mailgun API (free tier available)
- HTML emails with professional styling
- Fallback to mock mode for development
- Error handling and logging

✅ **Token Management**
- Time-limited tokens (15 minutes)
- Secure hash storage (not plaintext)
- Token revocation on use
- Token cleanup

✅ **User Management**
- Auto-creates user on first magic link use
- Preserves user data on subsequent logins
- Role assignment (default: "agent")
- Profile tracking

✅ **Security**
- Tokens are hashed before storage
- Links include both token and email (verification)
- Expiry enforcement
- One-time use only

## Configuration

### For Development (Mock Mode)
No configuration needed! The system automatically mocks email sending:
```
[MOCK EMAIL] Magic link sent to user@example.com
[MOCK EMAIL] Link: http://localhost:8001/api/auth/magic-link/verify?token=...
```

### For Production (Real Emails via Mailgun)

1. **Sign up for Mailgun** (free 100 emails/day tier):
   - Go to https://mailgun.com
   - Create account
   - Verify domain
   - Get API key and domain

2. **Update `.env` file**:
   ```env
   MAILGUN_API_KEY=your_api_key_from_mailgun
   MAILGUN_DOMAIN=your_domain.mailgun.org
   BASE_URL=https://your-app.com
   ```

3. **Deploy to production** (Render, Heroku, etc.)
   - Set environment variables in platform
   - Deploy code
   - Test magic link flow

## Testing

### Local Testing (with mock emails)
```bash
# Start server
cd d:\Project\support-portal-edgeworks
$env:DATABASE_URL = 'postgresql+psycopg2://...'
python -m uvicorn main:app --host 0.0.0.0 --port 8001
```

### Test Request
```bash
# Request magic link
curl -X POST http://localhost:8001/api/auth/magic-link/request \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com"}'

# Response:
# {
#   "status": "success",
#   "message": "Check your email for the magic link..."
# }
```

### Check Logs
The server logs will show:
```
[MOCK EMAIL] Magic link sent to test@example.com
[MOCK EMAIL] Link: http://localhost:8001/api/auth/magic-link/verify?token=abc123...&email=test@example.com
Magic link requested for: test@example.com
```

## Database Tables Used

### AuthMagicLink
- `id`: Auto-increment primary key
- `user_id`: Agent who owns the link
- `token_hash`: Hashed token (bcrypt-style)
- `expires_at`: Expiry datetime
- `created_at`: Creation timestamp
- `is_used`: Boolean flag (true after first use)

### Agent
- `user_id`: Unique identifier
- `email`: Email address
- `name`: Display name
- `department`: Department/role
- `created_at`: Account creation time

## Error Handling

### Invalid Email
```
Status: 400
{
  "detail": "Email required"
}
```

### Expired Link
```
Status: 401
{
  "detail": "Magic link expired"
}
```

### Verification Error
```
Status: 500
{
  "detail": "Magic link verification failed"
}
```

## Security Considerations

1. **Token Hashing**: Tokens are hashed before storage (not plaintext)
2. **Time Limit**: Links expire after 15 minutes
3. **One-Time Use**: Links cannot be reused
4. **HTTPS Only**: Should use HTTPS in production
5. **Email Validation**: Check email format before creating link
6. **Rate Limiting**: API includes rate limiting (20/min for chat, 100/min for general API)

## Email Template

The email includes:
- Professional header with app name
- Clear call-to-action button
- Raw link for manual entry
- Security notice with expiry time
- Footer with app info

HTML email template is in `app/utils/email_utils.py`

## Files Modified/Created

### Created:
- `app/utils/email_utils.py` - Email sending utilities

### Modified:
- `main.py` - Updated magic link request endpoint
- `.env` - Added email configuration

### No Breaking Changes
✅ All existing functionality preserved
✅ Backward compatible
✅ Works alongside other auth methods

## Deployment Instructions

### Render.com (Recommended)

1. Add to environment variables:
   ```
   DATABASE_URL=postgresql+...
   BASE_URL=https://your-app-name.onrender.com
   MAILGUN_API_KEY=your_key
   MAILGUN_DOMAIN=your_domain.mailgun.org
   ```

2. Deploy
3. Test magic link flow

### Heroku

1. Add config vars:
   ```
   heroku config:set DATABASE_URL="..."
   heroku config:set BASE_URL="https://your-app.herokuapp.com"
   heroku config:set MAILGUN_API_KEY="..."
   heroku config:set MAILGUN_DOMAIN="..."
   ```

2. Deploy with `git push heroku main`

### Azure App Service

1. Set application settings for all config variables
2. Deploy from GitHub/Azure DevOps
3. Configure custom domain

## API Reference

### POST /api/auth/magic-link/request
Request a magic link for email-based authentication

**Request:**
```json
{
  "email": "user@support.ai"
}
```

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Check your email for the magic link. If you don't see it, check your spam folder."
}
```

**Errors:**
- 400: Email required
- 500: Failed to create magic link

---

### GET /api/auth/magic-link/verify
Verify magic link and authenticate user

**Query Parameters:**
- `token` - Magic link token
- `email` - User email address

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "role": "agent",
  "name": "User Name",
  "email": "user@example.com"
}
```

**Errors:**
- 401: Invalid or expired magic link
- 500: Verification failed

## Troubleshooting

### Emails Not Sending in Production

1. **Check Mailgun Configuration**
   - Verify API key is correct
   - Verify domain is registered and verified
   - Check for typos in .env

2. **Check Email Address**
   - Ensure email is valid format
   - Check spam folder
   - Verify sender domain reputation

3. **Check Logs**
   - Review application logs for errors
   - Look for Mailgun API error responses

### Link Not Working

1. **Check Expiry**: Links expire after 15 minutes
2. **Check One-Time Use**: Link can only be used once
3. **Check Email/Token**: Both must match to verify
4. **Check Database**: Verify link exists in AuthMagicLink table

### Development Mode Issues

1. **Can't find mock email log?**
   - Check application stdout/stderr
   - Look for `[MOCK EMAIL]` prefix

2. **Link not showing in logs?**
   - Check server process is running
   - Enable verbose logging with `--log-level debug`

## Future Enhancements

- [ ] SMS-based magic links (Twilio/Bird)
- [ ] QR code magic links
- [ ] Multiple authentication factors
- [ ] Custom email templates
- [ ] Email branding customization
- [ ] Analytics on magic link usage
- [ ] Resend functionality
- [ ] Link lifetime configuration

## Support

For issues or questions:
1. Check logs for error messages
2. Review configuration in `.env`
3. Test with curl or Postman
4. Verify database connectivity
5. Check Mailgun account status (for production)
