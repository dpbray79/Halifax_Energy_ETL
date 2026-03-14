# Halifax Energy Forecasting — Cloud Deployment Guide

**100% Cloud Deployment with ZERO Local Storage**

Stack: Supabase (PostgreSQL) + Vercel (React) + GitHub Actions (R Model)

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Part 1: Supabase Database Setup](#part-1-supabase-database-setup)
3. [Part 2: Seed Historical Data](#part-2-seed-historical-data)
4. [Part 3: Vercel Dashboard Deployment](#part-3-vercel-dashboard-deployment)
5. [Part 4: GitHub Actions (Automated Model Training)](#part-4-github-actions-automated-model-training)
6. [Part 5: Verify Everything Works](#part-5-verify-everything-works)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- ✅ GitHub account (free)
- ✅ Supabase account (free tier: 500 MB database, 1 GB storage)
- ✅ Vercel account (free tier: unlimited deployments)
- ✅ Python 3.11+ installed locally (for one-time data seeding)
- ✅ Git installed

---

## Part 1: Supabase Database Setup

### Step 1.1: Create Supabase Project

1. Go to [https://supabase.com/dashboard](https://supabase.com/dashboard)
2. Click "New Project"
3. Fill in:
   - **Name**: `halifax-energy-project`
   - **Database Password**: Create strong password (save it!)
   - **Region**: Choose closest to you (e.g., `us-east-1`)
4. Click "Create new project"
5. Wait 2-3 minutes for provisioning

### Step 1.2: Run Schema SQL

1. In Supabase Dashboard, click **SQL Editor** (left sidebar)
2. Click **New query**
3. Open `/sql/supabase_schema.sql` from this project
4. Copy entire contents and paste into SQL Editor
5. Click **Run** (or press Cmd+Enter)
6. Verify success: Check **Table Editor** → you should see 6 tables:
   - `stg_nsp_load`
   - `stg_weather`
   - `fact_energy_weather`
   - `model_predictions`
   - `dim_date`
   - `etl_watermark`

### Step 1.3: Get Supabase Credentials

1. Go to **Settings** → **API** (left sidebar)
2. Copy these values (you'll need them):

```
Project URL:     https://your-project.supabase.co
anon public key: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

3. Go to **Settings** → **Database** → **Connection String**
4. Select **URI** tab, copy connection string:

```
postgresql://postgres:[YOUR-PASSWORD]@db.your-project.supabase.co:5432/postgres
```

5. Replace `[YOUR-PASSWORD]` with your actual database password

---

## Part 2: Seed Historical Data

### Step 2.1: Configure Local Environment

```bash
# Clone your repo (if not already)
git clone https://github.com/dpbray79/Halifax_Energy_ETL.git
cd Halifax_Energy_ETL

# Create Python virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2.2: Create .env File

Create `.env` in project root:

```bash
# Copy Supabase template
cp .env.supabase.example .env
```

Edit `.env` and fill in your Supabase credentials:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
DATABASE_URL=postgresql://postgres:YOUR-PASSWORD@db.your-project.supabase.co:5432/postgres
```

### Step 2.3: Run Historical Data Seed

```bash
# Seed 2023-2026 data (takes 10-15 minutes)
python scripts/seed_historical_data.py --start 2023-01-01
```

**Expected Output:**
```
✓ Connected to Supabase PostgreSQL
✓ Inserted 26,280 rows from CCEI HFED
✓ Inserted 26,280 weather rows
Coverage: 95.2%
```

### Step 2.4: Verify Data in Supabase

1. Go to Supabase Dashboard → **Table Editor**
2. Click `stg_nsp_load` → you should see ~26,000 rows
3. Run SQL query to check coverage:

```sql
SELECT TO_CHAR(datetime, 'YYYY-MM') AS month,
       COUNT(*) AS rows,
       ROUND(AVG(load_mw)::NUMERIC, 2) AS avg_load
FROM   stg_nsp_load
GROUP  BY TO_CHAR(datetime, 'YYYY-MM')
ORDER  BY month;
```

---

## Part 3: Vercel Dashboard Deployment

### Step 3.1: Push Code to GitHub

```bash
# Initialize git (if not already)
git init
git add .
git commit -m "Initial commit - Supabase + Vercel deployment"

# Push to GitHub
git remote add origin https://github.com/dpbray79/Halifax_Energy_ETL.git
git branch -M main
git push -u origin main
```

### Step 3.2: Deploy to Vercel

1. Go to [https://vercel.com/new](https://vercel.com/new)
2. Click "Import Git Repository"
3. Select `Halifax_Energy_ETL`
4. **Root Directory**: Change to `dashboard`
5. **Framework Preset**: Vite
6. **Build Command**: `npm run build`
7. **Output Directory**: `dist`

### Step 3.3: Add Environment Variables

Still in Vercel deployment settings:

1. Click **Environment Variables**
2. Add these variables:

```
VITE_SUPABASE_URL          = https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY     = your-anon-key
```

3. Click **Deploy**

### Step 3.4: Verify Deployment

1. Wait 2-3 minutes for build
2. Vercel will give you a URL: `https://halifax-energy-dashboard.vercel.app`
3. Open the URL → you should see the dashboard!
4. Check browser console for any errors

---

## Part 4: GitHub Actions (Automated Model Training)

### Step 4.1: Add GitHub Secrets

1. Go to your GitHub repo: `https://github.com/dpbray79/Halifax_Energy_ETL`
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**

Add these secrets (one at a time):

| Secret Name | Value |
|-------------|-------|
| `DATABASE_URL` | Your Supabase connection string |
| `VITE_SUPABASE_URL` | https://your-project.supabase.co |
| `VITE_SUPABASE_ANON_KEY` | Your anon key |
| `VERCEL_TOKEN` | Get from https://vercel.com/account/tokens |
| `VERCEL_ORG_ID` | Get from Vercel project settings |
| `VERCEL_PROJECT_ID` | Get from Vercel project settings |

### Step 4.2: Get Vercel Credentials

1. **VERCEL_TOKEN**:
   - Go to https://vercel.com/account/tokens
   - Click "Create Token"
   - Name: `GitHub Actions`
   - Copy token

2. **VERCEL_ORG_ID** and **VERCEL_PROJECT_ID**:
   - Go to your Vercel project
   - Click **Settings** → **General**
   - Scroll to **Project ID** and **Team ID** (Org ID)
   - Copy both

### Step 4.3: Test GitHub Actions

1. Go to **Actions** tab in GitHub repo
2. Click **Deploy to Vercel & Run R Model**
3. Click **Run workflow** → **Run workflow**
4. Watch the workflow run:
   - ✓ Deploy Dashboard
   - ✓ Train XGBoost Models (H1, H2, H3)
   - ✓ Upload model artifacts

**Scheduled Runs:**
- Daily at 4:00 AM UTC: Model retraining
- Daily at 6:00 AM UTC: Data extraction

---

## Part 5: Verify Everything Works

### Dashboard Verification

1. Open your Vercel URL
2. You should see:
   - ✅ Halifax map with 5 zones
   - ✅ Forecast chart with historical data
   - ✅ Performance metrics (after first model run)

### Database Verification

Run these queries in Supabase SQL Editor:

```sql
-- Row counts
SELECT 'stg_nsp_load' AS table_name, COUNT(*) AS rows FROM stg_nsp_load
UNION ALL
SELECT 'stg_weather', COUNT(*) FROM stg_weather
UNION ALL
SELECT 'model_predictions', COUNT(*) FROM model_predictions;

-- Latest actual
SELECT datetime, load_mw, source
FROM   stg_nsp_load
ORDER  BY datetime DESC
LIMIT  10;

-- Latest prediction
SELECT datetime, predicted_load_mw, forecast_horizon, run_rmse
FROM   model_predictions
ORDER  BY model_run_at DESC
LIMIT  10;
```

### Model Artifacts

1. Go to GitHub → **Actions** → latest workflow run
2. Click **Artifacts** → Download `model-artifacts`
3. Unzip and verify you have:
   - `xgb_model_H1.rds`
   - `xgb_model_H2.rds`
   - `xgb_model_H3.rds`

---

## Troubleshooting

### Issue: Dashboard shows "Failed to fetch data"

**Solution:**
1. Check Supabase credentials in Vercel environment variables
2. Verify Supabase database has data:
   ```sql
   SELECT COUNT(*) FROM stg_nsp_load;
   ```
3. Check browser console for error details

---

### Issue: GitHub Actions workflow fails on R model

**Error:** `Error: Package 'xgboost' not found`

**Solution:**
- GitHub Actions installs R packages automatically
- Check workflow logs for specific error
- Verify `DATABASE_URL` secret is set correctly

---

### Issue: Seed script fails with connection error

**Error:** `OperationalError: could not connect to server`

**Solution:**
1. Verify database password in `DATABASE_URL`
2. Check Supabase project is not paused (free tier pauses after 1 week inactivity)
3. Restart Supabase project in dashboard

---

### Issue: Vercel build fails

**Error:** `Module not found: @supabase/supabase-js`

**Solution:**
1. Verify `dashboard/package.json` includes `@supabase/supabase-js`
2. Delete `node_modules` and `package-lock.json`
3. Run `npm install` again
4. Push updated `package-lock.json` to GitHub

---

## Storage Usage Summary

| Component | Free Tier Limit | Your Usage | % Used |
|-----------|-----------------|------------|--------|
| **Supabase Database** | 500 MB | ~20 MB (3 years) | 4% |
| **Supabase Storage** | 1 GB | 0 MB (no CSVs stored) | 0% |
| **Supabase Bandwidth** | 2 GB/month | ~100 MB/month | 5% |
| **Vercel Bandwidth** | 100 GB/month | ~1 GB/month | 1% |
| **Vercel Builds** | Unlimited | ~3/day | - |
| **GitHub Actions** | 2000 min/month | ~60 min/month | 3% |

**Total Local Storage:** **0 bytes** ✅

---

## Next Steps

### Optional Enhancements

1. **Add Authentication**:
   - Enable Supabase Auth in dashboard
   - Restrict dashboard to authenticated users

2. **Custom Domain**:
   - Go to Vercel project → **Domains**
   - Add your custom domain (e.g., `energy.yourdomain.com`)

3. **Monitoring**:
   - Set up Supabase alerts for database usage
   - Add error tracking (Sentry, LogRocket)

4. **Real Halifax Zones**:
   - Replace placeholder GeoJSON with actual Halifax boundaries
   - Get data from Halifax Open Data Portal

---

## Support

**Documentation:**
- README.md — Project overview
- QUICKSTART.md — Local development setup (deprecated for cloud)
- PROJECT_SUMMARY.md — Architecture details

**Links:**
- Supabase Docs: https://supabase.com/docs
- Vercel Docs: https://vercel.com/docs
- GitHub Actions Docs: https://docs.github.com/actions

**Logs:**
- Vercel deployment logs: Vercel Dashboard → Deployments → [Latest]
- GitHub Actions logs: GitHub → Actions → [Workflow run]
- Supabase logs: Supabase Dashboard → Logs

---

**Congratulations!** Your Halifax Energy Forecasting system is now 100% cloud-deployed with zero local storage! 🎉

**Dylan Bray** | NSCC DBAS 3090 | March 2026
