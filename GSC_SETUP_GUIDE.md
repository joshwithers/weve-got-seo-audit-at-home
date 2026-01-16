# Google Search Console Integration - Setup Guide

## Overview

The SEO Audit Tool now integrates with Google Search Console (GSC) to provide traffic-prioritized insights. By connecting your GSC account, you can:

- **Prioritize issues by traffic impact** - Fix high-traffic pages first
- **See actual search queries** driving traffic to each page
- **Calculate opportunities** - Estimate potential traffic gains
- **Export traffic data** in all report formats (Markdown, HTML, JSON, CSV)

---

## Prerequisites

Before you begin, you'll need:

1. A Google Cloud Platform (GCP) account
2. Access to Google Search Console for your website
3. Python 3.8+ with the audit tool installed

---

## Step 1: Set Up Google Cloud Project

### 1.1 Create a New Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **"Select a project"** → **"New Project"**
3. Name it something like `"SEO Audit Tool"`
4. Click **"Create"**

### 1.2 Enable the Search Console API

1. In your new project, go to **"APIs & Services"** → **"Library"**
2. Search for `"Google Search Console API"`
3. Click on it and click **"Enable"**

---

## Step 2: Create OAuth 2.0 Credentials

### 2.1 Configure OAuth Consent Screen

1. Go to **"APIs & Services"** → **"OAuth consent screen"**
2. Select **"External"** (unless you have a Google Workspace account)
3. Click **"Create"**
4. Fill in required fields:
   - **App name:** `"SEO Audit Tool"`
   - **User support email:** Your email
   - **Developer contact email:** Your email
5. Click **"Save and Continue"**
6. On the **"Scopes"** page, click **"Save and Continue"** (no changes needed)
7. On **"Test users"**, add your Google email (the one with Search Console access)
8. Click **"Save and Continue"**

### 2.2 Create OAuth Client ID

1. Go to **"APIs & Services"** → **"Credentials"**
2. Click **"+ Create Credentials"** → **"OAuth client ID"**
3. **Application type:** Select **"Desktop app"**
4. **Name:** `"SEO Audit CLI"`
5. Click **"Create"**
6. Click **"Download JSON"** (save this file - you'll need it!)

---

## Step 3: Authenticate the Audit Tool

### 3.1 Save Your Credentials

Save the downloaded JSON file to a memorable location:

```bash
# Create a directory for credentials
mkdir -p ~/.seo_audit

# Move the downloaded file there
mv ~/Downloads/client_secret_*.json ~/.seo_audit/gsc_credentials.json
```

### 3.2 Run Authentication

```bash
audit gsc-auth --credentials ~/.seo_audit/gsc_credentials.json
```

**What happens:**
1. A browser window will open
2. Log in with your Google account (the one with Search Console access)
3. You'll see a warning: **"Google hasn't verified this app"**
   - Click **"Advanced"** → **"Go to SEO Audit Tool (unsafe)"**
4. Review permissions and click **"Continue"**
5. You'll see: **"The authentication flow has completed"**
6. Close the browser - your token is now saved!

### 3.3 Test Connection

Verify everything works:

```bash
audit gsc-test
```

You should see:
```
✅ Connected! You have access to X site(s):
  - https://example.com/
  - sc-domain:example.com
```

---

## Step 4: Usage

### Option A: Fetch GSC Data Separately

Fetch traffic data and store it in the database:

```bash
# Fetch last 90 days (default)
audit gsc-fetch https://example.com

# Fetch custom date range
audit gsc-fetch https://example.com --days 180

# Use specific database
audit gsc-fetch https://example.com --db my-audit.db
```

Then run your audit (reports will include traffic data):

```bash
audit run https://example.com --db my-audit.db
```

### Option B: Fetch During Audit

Run everything in one command:

```bash
# Crawl + Fetch GSC + Generate Report
audit run https://example.com --with-gsc

# Custom date range
audit run https://example.com --with-gsc --gsc-days 180

# Full example
audit run https://example.com \
  --with-gsc \
  --gsc-days 90 \
  --format html \
  --output report.html \
  --prepared-by "John Smith"
```

---

## What You'll See in Reports

### Traffic Summary

All reports now include overall traffic metrics:

```markdown
## 📊 Traffic Summary (Google Search Console)
**Date Range:** 2025-10-15 to 2026-01-15

- **Total Clicks:** 12,450
- **Total Impressions:** 456,789
- **Average CTR:** 2.73%
- **Pages with Traffic:** 127
```

### Traffic-Prioritized Issues

Issues are now sorted by traffic impact:

```markdown
### 🔴 High Priority (Errors)

#### High Traffic Pages

- [ ] **Missing Title** 🚨
  - Page: `https://example.com/blog/best-practices/`
  - Issue: Page is missing a title tag
  - 📈 **Traffic:** 1,234 clicks/month, Position: 5.2
  - 🔍 **Top Queries:**
    - "seo best practices" (Position 3.1, 890 clicks)
    - "website optimization tips" (Position 8.2, 344 clicks)
  - 💰 **Opportunity:** +370 clicks/month if moved to top 3

#### Other Pages
(Issues on pages without significant traffic)
```

### CSV Exports

Traffic data is included in CSV files:

```csv
URL,Status,Title,...,Traffic (Clicks/Month),Impressions,Average Position,CTR %,Top Query
https://example.com/,200,"Homepage",...,1234,45678,2.3,2.70,"brand name"
```

---

## Troubleshooting

### "Authentication failed" Error

**Cause:** Token expired or credentials invalid

**Solution:**
```bash
# Re-authenticate
audit gsc-auth --credentials ~/.seo_audit/gsc_credentials.json
```

### "No data found" Error

**Cause:** Site not in Search Console or no recent data

**Solutions:**
1. Verify site is added to Search Console: https://search.google.com/search-console
2. Check you used the correct URL format:
   - If property is `https://example.com/`, use `https://example.com`
   - If property is `sc-domain:example.com`, use `sc-domain:example.com`
3. Wait 24-48 hours after adding site to GSC for data to appear

### "Credentials file not found"

**Cause:** Wrong path or file not downloaded

**Solution:**
```bash
# Check if file exists
ls ~/.seo_audit/gsc_credentials.json

# If not, re-download from Google Cloud Console
# and save to the correct location
```

### Rate Limit Errors

**Cause:** Too many API requests

**Solution:**
- GSC API has quota limits (e.g., 1,200 requests/minute)
- Wait a few minutes and try again
- For large sites, use `--gsc-days 30` to fetch less data

---

## FAQ

### Q: How often should I refresh GSC data?

**A:** GSC data is typically 2-3 days delayed. Refresh weekly or before important audits.

### Q: Can I use this for multiple websites?

**A:** Yes! Each website can have its own database:

```bash
audit run https://site1.com --db site1.db --with-gsc
audit run https://site2.com --db site2.db --with-gsc
```

### Q: Does this work with domain properties?

**A:** Yes! Use the `sc-domain:` format:

```bash
audit gsc-fetch sc-domain:example.com
```

### Q: How much data is fetched?

**A:** By default:
- Last 90 days of traffic data
- All pages with traffic (up to 25,000)
- Top 25 queries per page (for top 100 pages)

### Q: Is my data secure?

**A:** Yes:
- Token stored locally: `~/.seo_audit/gsc_token.pickle`
- No data sent to external servers
- All processing happens on your machine

### Q: Can I revoke access?

**A:** Yes! Go to:
1. https://myaccount.google.com/permissions
2. Find "SEO Audit Tool"
3. Click "Remove Access"

Then delete the local token:
```bash
rm ~/.seo_audit/gsc_token.pickle
```

---

## Advanced Usage

### Custom Date Ranges

```bash
# Last 30 days (faster, less data)
audit run https://example.com --with-gsc --gsc-days 30

# Last 180 days (6 months)
audit run https://example.com --with-gsc --gsc-days 180

# Maximum: 16 months (GSC retention limit)
audit run https://example.com --with-gsc --gsc-days 480
```

### Workflow for Regular Audits

```bash
#!/bin/bash
# weekly-audit.sh

SITE="https://example.com"
DB="audit.db"
OUTPUT_DIR="./reports/$(date +%Y-%m-%d)"

# Clear old data
audit clear --db $DB

# Run fresh audit with GSC
audit run $SITE \
  --db $DB \
  --with-gsc \
  --gsc-days 90 \
  --format all \
  --export-dir $OUTPUT_DIR \
  --prepared-by "SEO Team"

echo "✓ Reports saved to: $OUTPUT_DIR"
```

### Separate Crawl and Export

For large sites, you may want to separate crawling and exporting:

```bash
# 1. Crawl (takes time)
audit run https://bigsite.com --db bigsite.db

# 2. Fetch GSC data
audit gsc-fetch https://bigsite.com --db bigsite.db

# 3. Export reports (instant)
audit export --db bigsite.db --format markdown
audit export --db bigsite.db --format html
audit export --db bigsite.db --format csv
```

---

## Support

If you encounter issues:

1. Check the troubleshooting section above
2. Verify your Google Cloud project setup
3. Ensure you have Search Console access for the site
4. Try re-authenticating: `audit gsc-auth`

For bugs or feature requests, report at: https://github.com/your-repo/issues

---

**Next Steps:**
- Phase 2: PageSpeed Insights integration (Core Web Vitals)
- Phase 3: AI Brand Visibility Report (ChatGPT, Claude, Gemini)
