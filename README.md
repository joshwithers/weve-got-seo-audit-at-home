# SEO Audit Engine

**Version 0.3.0** - A local-first SEO website audit tool with Google Search Console integration.

## What It Does

Crawls your website, identifies SEO issues, and generates traffic-prioritized reports using real data from Google Search Console.

**Key Features:**
- 🏠 **Local-First** - All data stays on your machine
- 📊 **Traffic-Prioritized** - Fix issues on high-traffic pages first
- 🔍 **Search Query Analysis** - See what people are searching for
- 💰 **Opportunity Calculation** - Estimate potential traffic gains
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

## Google Search Console Integration

Get traffic-prioritized insights by connecting to Google Search Console.

### One-Time Setup (5 minutes)

```bash
# 1. Authenticate
audit gsc-auth --credentials /path/to/credentials.json

# 2. Test connection
audit gsc-test
```

**See [GSC_SETUP_GUIDE.md](GSC_SETUP_GUIDE.md) for complete instructions.**

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

## What Gets Checked

### SEO Audit Checks

1. **Broken Links** - 404s and unreachable URLs
2. **Page Titles** - Missing, duplicate, too short/long
3. **Meta Descriptions** - Missing or problematic descriptions
4. **Headings Structure** - Missing or multiple H1 tags
5. **Redirects** - Redirect chains and loops

### Smart Features

- **File Filtering** - Automatically skips .pdf, .xml, .txt, etc.
- **robots.txt Support** - Respects crawl rules
- **URL Normalization** - Handles duplicates intelligently
- **Rate Limiting** - Configurable delays between requests

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
- Excel/Google Sheets
- Filtering and sorting
- Includes traffic columns

---

## Traffic Prioritization

When using `--with-gsc`, reports automatically:

1. **Sort by Traffic** - High-traffic pages shown first
2. **Show Top Queries** - See what people search for
3. **Calculate Opportunities** - Estimate traffic gains
4. **Add Traffic Summary** - Overall site metrics

**Example:**
```
Issue: Missing title on /blog/article/
Traffic: 890 clicks/month
Position: 5.2
Top Query: "wedding budget" (320 clicks)
Opportunity: +450 clicks/month if moved to top 3
```

---

## Common Issues

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
- Verify site is in Search Console
- Use correct property format:
  - Domain property: `sc-domain:example.com`
  - URL prefix: `https://example.com`

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

## Documentation

- **README.md** (this file) - Main documentation
- **GSC_SETUP_GUIDE.md** - Complete GSC setup walkthrough
- **CHANGELOG.md** - Version history
- **docs/** - Development and implementation notes

---

## Version History

### 0.3.0 (2026-01-15)
- Google Search Console integration
- Traffic-prioritized reporting
- Search query analysis
- Opportunity calculations
- All export formats enhanced

### 0.2.0 (2026-01-15)
- Markdown/HTML exports with to-do lists
- SEO Health Score (0-100)
- Custom branding
- File extension filtering

### 0.1.0 (2026-01-15)
- Initial release
- Core crawling engine
- 5 audit checks
- JSON/CSV exports

**See [CHANGELOG.md](CHANGELOG.md) for complete history.**

---

## License

[Your License Here]

## Support

For issues or questions:
1. Check this README
2. See GSC_SETUP_GUIDE.md for GSC setup
3. Review docs/ folder for implementation details

---

**Built for SEO professionals who want to do great work for their clients.**
