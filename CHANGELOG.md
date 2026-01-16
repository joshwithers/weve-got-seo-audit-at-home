# Changelog

All notable changes to this project will be documented in this file.

## [0.4.0] - 2026-01-17

### Added
- **Infrastructure & Security Checks** 🔒
  - SSL certificate validation with expiration warnings (<30 days)
  - Robots.txt crawl permission analysis
  - AI/LLM crawler detection (GPTBot, Claude-Web, Anthropic-AI, etc.)
  - Sitemap availability checks
  - Email deliverability validation (SPF/DMARC records)
- New dependency: `dnspython>=2.4.0` for DNS lookups

### Changed
- **Broken Links Check** - Removed "uncrawled URL" warnings (now only reports actionable 404s and errors)
- **Issue Reporting** - All issues now listed in full (removed "and X more" truncation)
- **Timestamps** - All timestamps now use local time instead of UTC
- **Export Reliability** - Added error handling to `--format all` to ensure all exports complete

### Fixed
- Format "all" now correctly generates HTML reports
- Infrastructure checks now correctly use seed URL from crawl metadata
- Database cleared of stale example.com data

### Technical
- New file: `audit_engine/checks/infrastructure.py` (399 lines)
- Modified: `audit_engine/checks/__init__.py` (added InfrastructureCheck)
- Modified: All datetime references changed from `utcnow()` to `now()`
- Updated documentation consolidated into single README.md
