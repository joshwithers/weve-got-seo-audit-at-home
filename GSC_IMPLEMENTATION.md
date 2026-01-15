# Google Search Console Implementation - Phase 1

## Status: In Progress 🚧

This document tracks the implementation of GSC integration.

## ✅ Completed

1. **Dependencies Added** (`requirements.txt`)
   - `google-auth`
   - `google-auth-oauthlib`
   - `google-auth-httplib2`
   - `google-api-python-client`

2. **GSC Module Created** (`gsc_integration.py`)
   - OAuth authentication flow
   - Token storage and refresh
   - Site listing
   - Data fetching (pages + queries)
   - Connection testing

3. **Database Schema Updated** (`database.py`)
   - `gsc_page_data` table (clicks, impressions, CTR, position)
   - `gsc_queries` table (queries per page)
   - Methods: `save_gsc_page_data()`, `save_gsc_queries()`, `get_gsc_page_data()`, `get_gsc_queries()`, `has_gsc_data()`

## 🔄 In Progress

4. **CLI Commands** (`cli.py`)
   - Need to add:
     - `audit gsc-auth` - Setup authentication
     - `audit gsc-test` - Test connection
     - `audit gsc-fetch` - Fetch data separately
     - `audit run --with-gsc` - Run audit with GSC data
     - `audit run --gsc-days N` - Specify date range

5. **Exporter Updates** (`exporter.py`)
   - Show traffic data in reports
   - Prioritize issues by traffic impact
   - Display top queries per page
   - Calculate opportunity metrics

## 📋 TODO

6. **URL Matching Logic**
   - Match GSC URLs to crawled pages
   - Handle URL normalization differences
   - Deal with trailing slashes, query params

7. **Traffic-Prioritized Reports**
   - Sort issues by traffic impact
   - Show "High Priority" for top landing pages
   - Calculate opportunity: "Fix this = +X clicks/month"

8. **Documentation**
   - Setup guide for OAuth credentials
   - Usage examples
   - Troubleshooting

## 🎯 Next Steps

1. Add `gsc-auth` command to CLI
2. Add `--with-gsc` flag to `run` command
3. Update exporter to show GSC data
4. Test with real GSC account
5. Update README with GSC instructions

## Usage (When Complete)

```bash
# One-time setup
audit gsc-auth --credentials /path/to/gsc_credentials.json

# Test connection
audit gsc-test

# Run audit with GSC data
audit run https://marriedbyjosh.com --with-gsc

# Specify custom date range
audit run https://marriedbyjosh.com --with-gsc --gsc-days 180
```

## Report Output (When Complete)

```markdown
# SEO Report of marriedbyjosh.com

## Traffic Summary (Last 90 Days)
- Total Clicks: 3,200
- Total Impressions: 125,000
- Average CTR: 2.56%

## High-Priority Issues (By Traffic Impact)

### 1. Missing Title on /blog/wedding-budget/
- **Traffic:** 450 clicks/month
- **Top Queries:**
  1. "wedding budget australia" - Position 3, 180 clicks
  2. "how much does wedding cost" - Position 5, 120 clicks
- **Opportunity:** +180 clicks/month if optimized to position 1

### 2. Duplicate Meta Description on Homepage
- **Traffic:** 1,234 clicks/month (Top landing page!)
- **Top Queries:**
  1. "brisbane celebrant" - Position 2, 890 clicks
  2. "wedding officiant brisbane" - Position 4, 344 clicks
- **Opportunity:** +15% CTR = +185 clicks/month
```
