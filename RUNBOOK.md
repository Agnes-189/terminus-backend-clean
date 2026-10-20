# Terminus Backend Operational Runbook & Launch Checklist

## Pre-Deployment Verification
1. Provision secrets (`JWT_SECRET`, `ORACLE_KEYPAIR_SECRET`, `DATABASE_URL`) in cloud secrets manager.
2. Ensure `ENVIRONMENT=production` and `DEBUG=false`.
3. Run Alembic database migrations: `alembic upgrade head`.

## Production Deployment
```bash
docker compose -f docker-compose.prod.yml up -d --build
Live Smoke Validation
Bash
BASE_URL="[https://api.terminus.network](https://api.terminus.network)" python scripts/validate_staging_e2e.py
