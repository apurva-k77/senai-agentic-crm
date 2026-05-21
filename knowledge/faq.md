# Product FAQ

## Integrations
- Slack: on roadmap Q3; use webhooks + Zapier today
- SSO: SAML 2.0 on Enterprise tier
- API: OpenAPI 3 spec at /docs/api/v3

## Data Export
- CSV/JSON export from Settings → Data; if export reports success but file empty, treat as **P0 bug** and escalate engineering

## Webhooks
- Retries: exponential backoff 1s, 2s, 4s, max 5 attempts
