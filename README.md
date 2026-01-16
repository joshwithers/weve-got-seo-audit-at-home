# We've got SEO Audit at home

## A locally run SEO Audit Engine

**Version 0.4.0** - A local-first SEO website audit tool with Google Search Console integration.

Crawls your website, identifies SEO issues, and generates traffic-prioritized reports using real data from Google Search Console.

**Key Features:**
- 🏠 **Local-First** - All data stays on your machine
- 📊 **Traffic-Prioritized** - Fix issues on high-traffic pages first
- 🔍 **Search Query Analysis** - See what people are searching for
- 💰 **Opportunity Calculation** - Estimate potential traffic gains
- 🔒 **Infrastructure Checks** - SSL, robots.txt, sitemap, email deliverability
- 📝 **Multiple Formats** - Markdown, HTML, JSON, CSV

---

## Quick Start

### Installation

```bash
cd seo-audit-engine
./install.sh
source venv/bin/activate
```

### Basic Usage

```bash
# Simple audit (no GSC required)
audit run https://example.com

# With Google Search Console traffic data
audit run https://example.com --with-gsc

# Full site audit
audit run https://example.com --max-pages 1000 --depth 5 --with-gsc --format html
```

---

## What Gets Checked

### 1. Broken Links
- 404 errors
- Unreachable URLs
- Only reports actionable issues (excludes uncrawled pages outside depth limit)

### 2. Page Titles
- Missing titles
- Duplicate titles
- Title length (too short/long)

### 3. Meta Descriptions
- Missing descriptions
- Duplicate descriptions
- Description length

### 4. Headings Structure
- Missing H1 tags
- Multiple H1 tags per page

### 5. Redirects
- Redirect chains
- Redirect loops

### 6. Infrastructure & Security
- **SSL Certificate** - Validates HTTPS, checks expiration dates (warns if <30 days)
- **Robots.txt Crawl Permissions** - Reports if your site allows search engine crawling
- **AI/LLM Crawler Permissions** - Identifies blocked/allowed AI crawlers (GPTBot, Claude-Web, Anthropic-AI, etc.)
- **Sitemap Availability** - Tests common sitemap locations and robots.txt declarations
- **Email Deliverability** - Validates SPF and DMARC records for domain reputation

---

## CLI Reference

### Main Commands

```bash
audit run <url> [OPTIONS]          # Run complete audit
audit export [OPTIONS]              # Export from existing data
audit checks                        # List available checks
audit clear                         # Clear database

# Google Search Console
audit gsc-auth --credentials <path> # One-time authentication
audit gsc-test                      # Test GSC connection
audit gsc-fetch <url>               # Fetch traffic data separately
```

### Common Options

```bash
--max-pages N       # Maximum pages to crawl (default: 1000)
--depth N           # Maximum crawl depth (default: 3)
--format FORMAT     # Output: markdown, html, json, csv, all
--with-gsc          # Include Google Search Console data
--gsc-days N        # Days of GSC data (default: 90)
--business-name     # Your business name for reports
--prepared-by       # Your name for reports
```

### Examples

```bash
# Deep crawl with traffic data
audit run https://example.com --max-pages 5000 --depth 10 --with-gsc

# Quick check (50 pages, 3 levels deep)
audit run https://example.com --max-pages 50

# All formats with branding
audit run https://example.com --format all \
  --business-name "Your Company" \
  --prepared-by "Your Name"

# Domain property (for GSC)
audit gsc-fetch sc-domain:example.com
```

---

## Google Search Console Integration

Get traffic-prioritized insights by connecting to Google Search Console.

### Setup (5 minutes)

#### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **"Select a project"** → **"New Project"**
3. Name it `"SEO Audit Tool"` and click **"Create"**

#### Step 2: Enable Search Console API

1. Go to **"APIs & Services"** → **"Library"**
2. Search for `"Google Search Console API"`
3. Click **"Enable"**

#### Step 3: Create OAuth Credentials

1. Go to **"APIs & Services"** → **"OAuth consent screen"**
2. Select **"External"** and click **"Create"**
3. Fill in:
   - **App name:** `"SEO Audit Tool"`
   - **User support email:** Your email
   - **Developer contact email:** Your email
4. Click through the remaining screens (no changes needed)
5. On **"Test users"**, add your Google email

6. Go to **"APIs & Services"** → **"Credentials"**
7. Click **"+ Create Credentials"** → **"OAuth client ID"**
8. **Application type:** **"Desktop app"**
9. **Name:** `"SEO Audit CLI"`
10. Click **"Create"** and **"Download JSON"**

#### Step 4: Authenticate

```bash
# Save credentials
mkdir -p ~/.seo_audit
mv ~/Downloads/client_secret_*.json ~/.seo_audit/gsc_credentials.json

# Authenticate
audit gsc-auth --credentials ~/.seo_audit/gsc_credentials.json
```

A browser will open:
1. Log in with your Google account
2. Click **"Advanced"** → **"Go to SEO Audit Tool (unsafe)"**
3. Click **"Continue"**
4. Close the browser when done

#### Step 5: Test Connection

```bash
audit gsc-test
```

You should see your connected sites listed.

### What You Get

**Without GSC:**
- List of all SEO issues
- Issues sorted by severity (errors, warnings, notices)

**With GSC (`--with-gsc`):**
- Issues prioritized by actual traffic
- Top search queries per page
- Traffic opportunities ("Fix this = +X clicks/month")
- Overall traffic summary

**Example Report:**
```markdown
## High Priority Issues

### High Traffic Pages

- Missing Title on /popular-page/
  Traffic: 1,234 clicks/month, Position: 5.2
  Top Queries: "keyword 1", "keyword 2"
  Opportunity: +370 clicks/month if moved to top 3
```

### Usage

```bash
# Fetch GSC data during audit
audit run https://example.com --with-gsc

# Fetch GSC data separately
audit gsc-fetch https://example.com --days 180

# Custom date range
audit run https://example.com --with-gsc --gsc-days 30
```

---

## Export Formats

### Markdown (Default)
```bash
audit run <url>
# Creates: audit_report.md
```
- GitHub-style checkboxes
- Traffic metrics and top queries
- Perfect for feeding to ChatGPT/Claude
- **All issues listed** - no truncation

### HTML
```bash
audit run <url> --format html
```
- Interactive checkboxes (saves state)
- Color-coded severity
- Client-ready reports

### JSON
```bash
audit run <url> --format json
```
- Machine-readable
- Full data structure
- API integrations

### CSV
```bash
audit run <url> --format csv
```
- Excel/Google Sheets compatible
- Filtering and sorting
- Includes traffic columns

### All Formats
```bash
audit run <url> --format all --export-dir ./reports
```
Exports JSON, Markdown, HTML, and CSV files to the specified directory.

---

## Troubleshooting

### "Only 100 pages crawled"
```bash
# Increase depth to reach more pages
audit run <url> --depth 5

# Or increase page limit
audit run <url> --max-pages 5000
```

### "Not authenticated with GSC"
```bash
# When using --with-gsc, authenticate first
audit gsc-auth --credentials /path/to/credentials.json

# Or authenticate during audit (you'll be prompted)
```

### "No GSC data found"
- Verify site is in Search Console: https://search.google.com/search-console
- Use correct property format:
  - Domain property: `sc-domain:example.com`
  - URL prefix: `https://example.com`
- Wait 24-48 hours after adding site for data to appear

### "Credentials file not found"
```bash
# Check if file exists
ls ~/.seo_audit/gsc_credentials.json

# If not, re-download from Google Cloud Console
```

### Rate Limit Errors
- GSC API has quota limits (1,200 requests/minute)
- Wait a few minutes and try again
- For large sites, use `--gsc-days 30` to fetch less data

---

## Files and Data

### Generated Files
- `audit.db` - SQLite database with all crawl data
- `audit_report.md/html/json` - Report files
- `audit_issues.csv` - Issues spreadsheet
- `audit_pages.csv` - Pages spreadsheet

### Stored Data
- `~/.seo_audit/gsc_token.pickle` - GSC authentication token
- `~/.seo_audit/gsc_credentials.json` - GSC OAuth credentials

---

## FAQ

### How often should I refresh GSC data?
GSC data is typically 2-3 days delayed. Refresh weekly or before important audits.

### Can I use this for multiple websites?
Yes! Each website can have its own database:

```bash
audit run https://site1.com --db site1.db --with-gsc
audit run https://site2.com --db site2.db --with-gsc
```

### Does this work with domain properties?
Yes! Use the `sc-domain:` format:

```bash
audit gsc-fetch sc-domain:example.com
```

### How much data is fetched?
By default:
- Last 90 days of traffic data
- All pages with traffic (up to 25,000)
- Top 25 queries per page (for top 100 pages)

### Is my data secure?
Yes:
- Token stored locally: `~/.seo_audit/gsc_token.pickle`
- No data sent to external servers
- All processing happens on your machine

### Can I revoke access?
Yes:
1. Go to https://myaccount.google.com/permissions
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

For large sites, separate crawling and exporting:

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

## License

MIT License

---

**Built for SEO professionals who want local-first, traffic-prioritized website audits.**
