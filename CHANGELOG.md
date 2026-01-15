# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
