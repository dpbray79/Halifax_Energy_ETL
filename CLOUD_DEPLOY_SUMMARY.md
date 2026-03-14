# Cloud Deployment Summary

## Architecture Overview

```
┌────────────────────────────────────────────────────────────┐
│              Halifax Energy Forecasting System              │
│              100% Cloud • Zero Local Storage                │
└────────────────────────────────────────────────────────────┘

┌─────────────────┐        ┌──────────────────┐       ┌───────────────┐
│   User Browser  │───────→│  Vercel (React)  │──────→│   Supabase    │
│  (Any Device)   │  HTTPS │   5173 → CDN     │  API  │  PostgreSQL   │
└─────────────────┘        └──────────────────┘       └───────────────┘
                                    │                          ▲
                                    │                          │
                                    ▼                          │
                          ┌──────────────────┐                │
                          │ GitHub Actions   │ ───────────────┘
                          │ • R XGBoost      │   Daily ETL
                          │ • Data Extract   │   & Model Run
                          └──────────────────┘
```

---

## Components

### 1. Supabase (Database + API)
- **Service**: PostgreSQL 15 (serverless)
- **Free Tier**: 500 MB database, 1 GB storage, 2 GB bandwidth/month
- **Usage**: ~20 MB database (3 years data), 0 MB storage
- **Features**:
  - Auto-generated REST API
  - Real-time subscriptions (WebSocket replacement)
  - Built-in auth (not enabled yet)
  - Automatic backups

**Tables:**
- `stg_nsp_load` — Raw energy load data
- `stg_weather` — Halifax weather observations
- `fact_energy_weather` — Gold table (ML features)
- `model_predictions` — XGBoost forecasts
- `dim_date` — Date dimension
- `etl_watermark` — Incremental load tracking

### 2. Vercel (React Dashboard)
- **Service**: Static site hosting + CDN
- **Free Tier**: Unlimited deployments, 100 GB bandwidth/month
- **Usage**: ~1 GB bandwidth/month
- **Features**:
  - Automatic HTTPS
  - Global CDN
  - Git-based deployments
  - Environment variable management

**URL**: `https://halifax-energy-dashboard.vercel.app`

### 3. GitHub Actions (Automation)
- **Service**: CI/CD + cron jobs
- **Free Tier**: 2000 minutes/month
- **Usage**: ~60 minutes/month
- **Workflows**:
  - `deploy.yml` — Deploy dashboard + run R model
  - Scheduled: Daily 4:00 AM UTC (model retrain)
  - Scheduled: Daily 6:00 AM UTC (data extraction)

---

## Deployment Flow

### Initial Setup (One-Time)

1. **Supabase** → Create project, run schema SQL
2. **Local** → Seed historical data (2023-2026)
3. **GitHub** → Push code to repository
4. **Vercel** → Deploy React dashboard
5. **GitHub Actions** → Add secrets, enable workflows

### Daily Operations (Automated)

```
06:00 UTC → Extract CCEI HFED load data
         → Extract Environment Canada weather
         → Insert into stg_nsp_load, stg_weather

04:00 UTC → Run R XGBoost model (H1, H2, H3)
         → Generate predictions
         → Insert into model_predictions
         → Upload model artifacts

On Push → Rebuild Vercel dashboard
       → Deploy to CDN
```

---

## Cost Breakdown (Free Tier)

| Service | Free Tier | Usage | Cost |
|---------|-----------|-------|------|
| **Supabase** | 500 MB DB + 1 GB storage | 20 MB | $0 |
| **Vercel** | 100 GB bandwidth | 1 GB/mo | $0 |
| **GitHub Actions** | 2000 min/month | 60 min/mo | $0 |
| **Total** | - | - | **$0/month** |

---

## Data Storage

### Cloud (Supabase):
- Database: 20 MB (3 years hourly data)
- Storage: 0 MB (no CSV files stored)

### Local:
- **0 bytes** — No local storage required!

---

## Access

- **Dashboard**: `https://halifax-energy-dashboard.vercel.app`
- **Supabase**: `https://supabase.com/dashboard/project/YOUR_PROJECT`
- **GitHub**: `https://github.com/dpbray79/Halifax_Energy_ETL`
- **Vercel**: `https://vercel.com/dashboard`

---

## Secrets Management

### GitHub Secrets (Required):
```
DATABASE_URL              → postgresql://...
VITE_SUPABASE_URL         → https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY    → eyJhbGciOiJI...
VERCEL_TOKEN              → (from Vercel account tokens)
VERCEL_ORG_ID             → (from Vercel project settings)
VERCEL_PROJECT_ID         → (from Vercel project settings)
```

### Vercel Environment Variables:
```
VITE_SUPABASE_URL
VITE_SUPABASE_ANON_KEY
```

---

## Performance

### Current (3 Years Data):
- Database size: 20 MB
- Dashboard load time: < 2s
- API response time: < 100ms
- Real-time updates: Instant (Supabase Realtime)

### Projected (10 Years Data):
- Database size: 60 MB (12% of free tier)
- No performance degradation expected

---

## Monitoring

### Logs:
- **Supabase**: Dashboard → Logs
- **Vercel**: Dashboard → Deployments → [Latest] → Logs
- **GitHub Actions**: Actions tab → [Workflow run] → Logs

### Alerts:
- Vercel: Email on deployment failure
- GitHub Actions: Email on workflow failure
- Supabase: Dashboard usage warnings

---

## Backup & Recovery

### Automatic Backups:
- **Supabase**: Daily backups (7-day retention on free tier)
- **Model Artifacts**: Stored in GitHub Actions artifacts (30-day retention)

### Point-in-Time Recovery:
- Supabase Pro feature (upgrade if needed)

### Manual Backups:
```sql
-- Export data from Supabase SQL Editor
SELECT * FROM stg_nsp_load;
-- Save as CSV
```

---

## Scaling Path (If Needed)

### Supabase Free → Pro ($25/month):
- 8 GB database (40x increase)
- 250 GB bandwidth (125x increase)
- Point-in-time recovery
- Daily backups (30-day retention)

### Vercel Free → Pro ($20/month):
- Unlimited bandwidth
- Analytics
- Custom domains
- Preview deployments

### GitHub Actions (Keep Free):
- 2000 min/month is sufficient
- Can add self-hosted runners if needed

---

## Next Steps

### Immediate:
1. ✅ Deploy to Supabase
2. ✅ Deploy to Vercel
3. ✅ Set up GitHub Actions
4. ✅ Verify automated workflows

### Future Enhancements:
- [ ] Add authentication (Supabase Auth)
- [ ] Custom domain
- [ ] Real Halifax zone boundaries
- [ ] Email alerts for model performance degradation
- [ ] API rate limiting
- [ ] Caching layer (Redis)

---

**Status**: ✅ **PRODUCTION READY**

**Deployed**: March 2026
**Author**: Dylan Bray
**Course**: NSCC DBAS 3090
