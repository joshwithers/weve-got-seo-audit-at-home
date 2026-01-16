# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-01-15

### Added - Google Search Console Integration 🎉
- **GSC Authentication** - OAuth 2.0 flow with token storage and auto-refresh
- **Traffic Data Fetching** - Retrieve clicks, impressions, CTR, and position data
- **Search Query Analysis** - Top 25 queries per page with metrics
- **Traffic-Prioritized Reports** - Issues sorted by page traffic impact
- **Opportunity Calculations** - Estimate potential traffic gains from fixes
- **URL Matching** - Smart normalization to match GSC URLs with crawled pages
- **Traffic Summary** - Overall site metrics in all report formats
- CLI commands:
  - `audit gsc-auth` - One-time Google authentication
  - `audit gsc-test` - Verify GSC connection
  - `audit gsc-fetch` - Fetch traffic data separately
- CLI flags:
  - `--with-gsc` - Include GSC data during audit
  - `--gsc-days N` - Specify date range (default: 90 days)
- **Enhanced Exports**:
  - Markdown: Traffic metrics, top queries, and opportunities per issue
  - HTML: Traffic info boxes with green backgrounds
  - JSON: Full traffic data in nested structure
  - CSV: 5 new columns (clicks, impressions, position, CTR, top query)
- Database tables:
  - `gsc_page_data` - Page-level traffic metrics
  - `gsc_queries` - Query-level data per page
- **Comprehensive Documentation**:
  - `GSC_SETUP_GUIDE.md` - Complete setup instructions
  - README.md updated with GSC section
  - Troubleshooting guide

### Changed
- Reports now show "High Traffic Pages" sections
- Issues grouped by traffic (high-traffic pages listed first)
- All export formats include optional traffic data
- CSV exports now have 11 columns (was 6 for issues, 11 for pages)

### Technical Details
- New file: `audit_engine/gsc_integration.py` (273 lines)
- Modified: `cli.py`, `database.py`, `exporter.py`
- Dependencies: Added 4 Google API libraries
- Token storage: `~/.seo_audit/gsc_token.pickle`

## [0.2.0] - 2026-01-15

### Added
- **Markdown export** with GitHub-style to-do list checkboxes
- **HTML export** with interactive checkboxes and modern UI
- **SEO Health Score** (0-100) based on issue severity
- **Custom branding** - Add business name and "prepared by" credits to all reports
- **File extension filtering** - Automatically skip .pdf, .epub, .xml, .txt, .zip files
- Report titles now show domain name: "SEO Report of domain.com"
- Interactive HTML features with localStorage for checkbox persistence
- Prioritized action items (High/Medium/Low priority)
- Issue breakdown by type in reports
- Color-coded severity indicators in HTML

### Changed
- **Default export format is now Markdown** (was JSON)
- Export formats now include: `json`, `markdown`, `html`, `csv`, `all`
- CLI options: Added `--business-name` and `--prepared-by` flags
- Reports are now optimized for feeding to LLMs
- Improved report structure with executive summaries

### Fixed
- DateTime parsing bug when retrieving data from SQLite
- Proper ISO timestamp formatting in all exports

## [0.1.0] - 2026-01-15

### Added
- Initial release of SEO Audit Engine
- Core crawling engine with robots.txt support
- SQLite database storage
- 5 audit checks:
  - Broken links detection
  - Page titles analysis (missing, duplicate, length)
  - Meta description checks
  - Heading structure analysis (H1)
  - Redirect chain detection
- CLI interface with `audit` command
- JSON export functionality
- CSV export functionality
- Configurable crawl depth and page limits
- Rate limiting with configurable delay
- Comprehensive documentation

### Features
- Local-first architecture (no external dependencies)
- Modular audit check system
- Deterministic output
- Breadth-first crawling
- URL normalization
- Content hash for duplicate detection
