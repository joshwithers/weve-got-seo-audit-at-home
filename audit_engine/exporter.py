"""
Export audit results to JSON, CSV, Markdown, and HTML formats.
"""

import json
import csv
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
from collections import defaultdict
from urllib.parse import urlparse

from .database import Database
from .models import Issue, Page, Severity


class Exporter:
    """Handles exporting audit data to various formats."""

    def __init__(self, database: Database, business_name: str = "SEO Audit Engine", prepared_by: str = ""):
        self.db = database
        self.business_name = business_name
        self.prepared_by = prepared_by
        self._gsc_data = None  # Cache GSC data
        self._has_gsc = None   # Cache GSC availability
        self._backlinks_data = None  # Cache backlinks data
        self._has_backlinks = None  # Cache backlinks availability

    def _has_gsc_data(self) -> bool:
        """Check if GSC data is available."""
        if self._has_gsc is None:
            self._has_gsc = self.db.has_gsc_data()
        return self._has_gsc

    def _get_gsc_data(self) -> dict:
        """Get all GSC data (cached)."""
        if self._gsc_data is None:
            self._gsc_data = self.db.get_gsc_page_data()
        return self._gsc_data

    def _normalize_url_for_matching(self, url: str) -> str:
        """
        Normalize URL for matching between crawled pages and GSC data.

        GSC and crawlers may format URLs differently:
        - Trailing slashes: /page vs /page/
        - Query params: /page?utm=... vs /page
        - Fragments: /page#section vs /page
        - Protocol: http vs https
        """
        parsed = urlparse(url)

        # Normalize path (remove trailing slash except for root)
        path = parsed.path.rstrip('/') if parsed.path != '/' else '/'

        # Build normalized URL (scheme + netloc + path, ignore query/fragment)
        normalized = f"{parsed.scheme}://{parsed.netloc}{path}"

        return normalized

    def _match_gsc_to_page(self, page_url: str) -> Optional[dict]:
        """
        Find matching GSC data for a crawled page.
        Returns GSC metrics + queries if found.
        """
        if not self._has_gsc_data():
            return None

        gsc_data = self._get_gsc_data()
        normalized_page = self._normalize_url_for_matching(page_url)

        # Try exact match first
        if page_url in gsc_data:
            result = gsc_data[page_url].copy()
            result['queries'] = self.db.get_gsc_queries(page_url)
            return result

        # Try normalized match
        for gsc_url, metrics in gsc_data.items():
            if self._normalize_url_for_matching(gsc_url) == normalized_page:
                result = metrics.copy()
                result['queries'] = self.db.get_gsc_queries(gsc_url)
                return result

        return None

    def _get_traffic_summary(self) -> Optional[dict]:
        """Get overall traffic summary from GSC data."""
        if not self._has_gsc_data():
            return None

        gsc_data = self._get_gsc_data()
        if not gsc_data:
            return None

        total_clicks = sum(d['clicks'] for d in gsc_data.values())
        total_impressions = sum(d['impressions'] for d in gsc_data.values())
        avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0

        # Get date range from first entry
        first_entry = next(iter(gsc_data.values()))
        date_range = first_entry.get('date_range', {})

        return {
            'total_clicks': total_clicks,
            'total_impressions': total_impressions,
            'avg_ctr': avg_ctr,
            'date_range': date_range,
            'pages_with_traffic': len(gsc_data)
        }

    def _calculate_opportunity(self, gsc_data: dict) -> Optional[str]:
        """
        Calculate traffic opportunity for a page.
        Estimates potential traffic gain if position improves.
        """
        if not gsc_data or 'position' not in gsc_data:
            return None

        position = gsc_data['position']
        clicks = gsc_data['clicks']
        impressions = gsc_data['impressions']

        # If already in top 3, opportunity is limited
        if position <= 3:
            return "Already in top 3 positions"

        # Estimate CTR improvement if moved to top 3
        # Rough estimates: position 1 ≈ 30% CTR, position 2 ≈ 15% CTR, position 3 ≈ 10% CTR
        current_ctr = (clicks / impressions) if impressions > 0 else 0
        target_ctr = 0.15  # Target position 2

        if current_ctr < target_ctr:
            potential_clicks = int(impressions * target_ctr) - clicks
            if potential_clicks > 10:
                return f"+{potential_clicks} clicks/month if moved to top 3"

        return None

    def _has_backlinks_data(self, domain: str = None) -> bool:
        """Check if backlinks data is available."""
        if self._has_backlinks is None:
            self._has_backlinks = self.db.has_cc_backlinks(domain)
        return self._has_backlinks

    def _get_backlinks_data(self, domain: str) -> Optional[dict]:
        """
        Get backlinks summary for domain.

        Returns:
            dict with total_domains, total_links, avg_quality, top_backlinks, graph_date
        """
        if not self.db.has_cc_backlinks(domain):
            return None

        backlinks = self.db.get_cc_backlinks(domain, limit=50)

        if not backlinks:
            return None

        total = len(backlinks)
        avg_quality = sum(bl['quality_score'] for bl in backlinks) / total if total > 0 else 0
        total_links = sum(bl['link_count'] for bl in backlinks)

        return {
            'total_domains': total,
            'total_links': total_links,
            'avg_quality': avg_quality,
            'top_backlinks': backlinks[:20],
            'graph_date': backlinks[0]['graph_date'] if backlinks else None
        }

    def export_json(self, output_path: str = "audit_report.json") -> None:
        """
        Export complete audit report as JSON.
        Includes pages, issues, and summary statistics.
        """
        pages = self.db.get_all_pages()
        issues = self.db.get_all_issues()

        # Get domain from first page
        domain = pages[0].url if pages else "Unknown"
        domain_name = urlparse(domain).netloc

        # Get traffic summary
        traffic_summary = self._get_traffic_summary()

        # Get backlinks summary
        backlinks_summary = self._get_backlinks_data(domain_name)

        # Build the report structure
        report = {
            "generated_at": datetime.now().isoformat(),
            "report_title": f"SEO Report of {domain_name}",
            "business_name": self.business_name,
            "prepared_by": self.prepared_by if self.prepared_by else None,
            "summary": {
                "total_pages": len(pages),
                "total_issues": len(issues),
                "errors": sum(1 for i in issues if i.severity.value == "error"),
                "warnings": sum(1 for i in issues if i.severity.value == "warning"),
                "notices": sum(1 for i in issues if i.severity.value == "notice"),
                "traffic": traffic_summary,  # Add GSC summary
                "backlinks": backlinks_summary  # Add backlinks summary
            },
            "pages": [
                {
                    "url": page.url,
                    "status_code": page.status_code,
                    "title": page.title,
                    "meta_description": page.meta_description,
                    "canonical": page.canonical,
                    "robots_meta": page.robots_meta,
                    "h1_count": page.h1_count,
                    "h1_text": page.h1_text,
                    "redirect_to": page.redirect_to,
                    "depth": page.depth,
                    "crawled_at": page.crawled_at.isoformat() if page.crawled_at else None,
                    "traffic": self._match_gsc_to_page(page.url)  # Add GSC data per page
                }
                for page in pages
            ],
            "issues": [
                {
                    "issue_type": issue.issue_type,
                    "severity": issue.severity.value,
                    "description": issue.description,
                    "affected_url": issue.affected_url,
                    "details": issue.details,
                    "created_at": issue.created_at.isoformat() if issue.created_at else None,
                }
                for issue in issues
            ],
        }

        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"JSON report exported to: {output_path}")

    def export_issues_csv(self, output_path: str = "audit_issues.csv") -> None:
        """Export issues as CSV for easy filtering and analysis."""
        issues = self.db.get_all_issues()

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Header (with GSC columns)
            writer.writerow([
                "Issue Type",
                "Severity",
                "Description",
                "Affected URL",
                "Details",
                "Created At",
                "Traffic (Clicks/Month)",
                "Impressions",
                "Average Position",
                "CTR %",
                "Top Query"
            ])

            # Data rows
            for issue in issues:
                # Get traffic data if available
                gsc_data = self._match_gsc_to_page(issue.affected_url) if issue.affected_url else None

                clicks = gsc_data['clicks'] if gsc_data else ""
                impressions = gsc_data['impressions'] if gsc_data else ""
                position = f"{gsc_data['position']:.1f}" if gsc_data else ""
                ctr = f"{gsc_data['ctr'] * 100:.2f}" if gsc_data else ""
                top_query = gsc_data['queries'][0]['query'] if gsc_data and gsc_data.get('queries') else ""

                writer.writerow([
                    issue.issue_type,
                    issue.severity.value,
                    issue.description,
                    issue.affected_url or "",
                    json.dumps(issue.details) if issue.details else "",
                    issue.created_at.isoformat() if issue.created_at else "",
                    clicks,
                    impressions,
                    position,
                    ctr,
                    top_query
                ])

        print(f"Issues CSV exported to: {output_path}")

    def export_pages_csv(self, output_path: str = "audit_pages.csv") -> None:
        """Export pages as CSV for analysis."""
        pages = self.db.get_all_pages()

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Header (with GSC columns)
            writer.writerow([
                "URL",
                "Status Code",
                "Title",
                "Meta Description",
                "Canonical",
                "Robots Meta",
                "H1 Count",
                "H1 Text",
                "Redirect To",
                "Depth",
                "Crawled At",
                "Traffic (Clicks/Month)",
                "Impressions",
                "Average Position",
                "CTR %",
                "Top Query"
            ])

            # Data rows
            for page in pages:
                # Get traffic data if available
                gsc_data = self._match_gsc_to_page(page.url)

                clicks = gsc_data['clicks'] if gsc_data else ""
                impressions = gsc_data['impressions'] if gsc_data else ""
                position = f"{gsc_data['position']:.1f}" if gsc_data else ""
                ctr = f"{gsc_data['ctr'] * 100:.2f}" if gsc_data else ""
                top_query = gsc_data['queries'][0]['query'] if gsc_data and gsc_data.get('queries') else ""

                writer.writerow([
                    page.url,
                    page.status_code or "",
                    page.title or "",
                    page.meta_description or "",
                    page.canonical or "",
                    page.robots_meta or "",
                    page.h1_count,
                    page.h1_text or "",
                    page.redirect_to or "",
                    page.depth,
                    page.crawled_at.isoformat() if page.crawled_at else "",
                    clicks,
                    impressions,
                    position,
                    ctr,
                    top_query
                ])

        print(f"Pages CSV exported to: {output_path}")

    def export_markdown(self, output_path: str = "audit_report.md") -> None:
        """
        Export audit report as Markdown with actionable to-do list.
        Perfect for human reading or feeding to LLMs.
        """
        pages = self.db.get_all_pages()
        issues = self.db.get_all_issues()

        # Group issues by severity
        issues_by_severity = defaultdict(list)
        for issue in issues:
            issues_by_severity[issue.severity].append(issue)

        # Group issues by type
        issues_by_type = defaultdict(list)
        for issue in issues:
            issues_by_type[issue.issue_type].append(issue)

        # Count statistics
        total_pages = len(pages)
        total_issues = len(issues)
        errors = len(issues_by_severity[Severity.ERROR])
        warnings = len(issues_by_severity[Severity.WARNING])
        notices = len(issues_by_severity[Severity.NOTICE])

        # Get domain from first page
        domain = urlparse(pages[0].url).netloc if pages else "Unknown"

        # Get traffic summary
        traffic_summary = self._get_traffic_summary()

        # Get backlinks summary
        backlinks_summary = self._get_backlinks_data(domain)

        # Start building markdown
        md = []
        md.append(f"# SEO Report of {domain}\n")
        if self.prepared_by:
            md.append(f"**Prepared by:** {self.prepared_by}\n")
        md.append(f"**Generated:** {datetime.now().strftime('%B %d, %Y at %H:%M')}\n")
        md.append("---\n")

        # Traffic Summary (if available)
        if traffic_summary:
            md.append("## 📊 Traffic Summary (Google Search Console)\n")
            date_range = traffic_summary['date_range']
            md.append(f"**Date Range:** {date_range.get('start', 'N/A')} to {date_range.get('end', 'N/A')}\n")
            md.append(f"- **Total Clicks:** {traffic_summary['total_clicks']:,}")
            md.append(f"- **Total Impressions:** {traffic_summary['total_impressions']:,}")
            md.append(f"- **Average CTR:** {traffic_summary['avg_ctr']:.2f}%")
            md.append(f"- **Pages with Traffic:** {traffic_summary['pages_with_traffic']:,}\n")
            md.append("---\n")

        # Backlinks Summary (if available)
        if backlinks_summary:
            md.append("## 🔗 Backlink Profile (Common Crawl)\n")
            md.append(f"**Graph Date:** {backlinks_summary['graph_date']}\n")
            md.append(f"- **Referring Domains:** {backlinks_summary['total_domains']:,}")
            md.append(f"- **Total Links:** {backlinks_summary['total_links']:,}")
            md.append(f"- **Average Quality:** {backlinks_summary['avg_quality']:.2f}/1.0\n")

            md.append("### Top Referring Domains\n")
            md.append("| Domain | Links | Quality |\n")
            md.append("|--------|-------|----------|\n")

            for bl in backlinks_summary['top_backlinks'][:20]:
                md.append(f"| {bl['referring_domain']} | {bl['link_count']} | {bl['quality_score']:.2f} |")

            md.append("\n---\n")

        # Executive Summary
        md.append("## Executive Summary\n")
        md.append(f"- **Total Pages Crawled:** {total_pages}")
        md.append(f"- **Total Issues Found:** {total_issues}")
        md.append(f"  - 🔴 **Errors:** {errors} (critical issues)")
        md.append(f"  - 🟡 **Warnings:** {warnings} (should fix)")
        md.append(f"  - 🔵 **Notices:** {notices} (improvements)")
        md.append("")

        # Health Score (scaled by pages)
        if total_pages > 0:
            # Calculate issue rate per page, weighted by severity
            issue_rate = ((errors * 3) + (warnings * 2) + (notices * 1)) / total_pages
            # Scale to 0-100 (0 issues = 100, higher issue rate = lower score)
            # Using exponential decay so small issue rates still give good scores
            health_score = max(0, min(100, 100 - (issue_rate * 25)))
            md.append(f"**SEO Health Score:** {health_score:.1f}/100\n")

        md.append("---\n")

        # TO-DO LIST (Traffic-Prioritized)
        md.append("## 🎯 Action Items (To-Do List)\n")
        md.append("*Copy this section to track your fixes*\n")

        # Helper function to add traffic info to issue
        def add_issue_with_traffic(issue, severity_emoji=""):
            md.append(f"- [ ] **{issue.issue_type.replace('_', ' ').title()}** {severity_emoji}")
            md.append(f"  - Page: `{issue.affected_url}`")
            md.append(f"  - Issue: {issue.description}")

            # Add traffic data if available
            if issue.affected_url:
                gsc_data = self._match_gsc_to_page(issue.affected_url)
                if gsc_data:
                    md.append(f"  - 📈 **Traffic:** {gsc_data['clicks']:,} clicks/month, Position: {gsc_data['position']:.1f}")

                    # Show top queries
                    if gsc_data.get('queries'):
                        top_queries = gsc_data['queries'][:3]
                        md.append(f"  - 🔍 **Top Queries:**")
                        for q in top_queries:
                            md.append(f"    - \"{q['query']}\" (Position {q['position']:.1f}, {q['clicks']} clicks)")

                    # Calculate opportunity
                    opportunity = self._calculate_opportunity(gsc_data)
                    if opportunity:
                        md.append(f"  - 💰 **Opportunity:** {opportunity}")

            if issue.details:
                md.append(f"  - Details: {self._format_details(issue.details)}")
            md.append("")

        # Errors (High Priority) - Sort by traffic impact
        if issues_by_severity[Severity.ERROR]:
            # Sort errors by traffic (pages with traffic first)
            errors_list = issues_by_severity[Severity.ERROR]
            errors_with_traffic = []
            errors_without_traffic = []

            for issue in errors_list:
                if issue.affected_url:
                    gsc_data = self._match_gsc_to_page(issue.affected_url)
                    if gsc_data and gsc_data.get('clicks', 0) > 0:
                        errors_with_traffic.append((issue, gsc_data['clicks']))
                    else:
                        errors_without_traffic.append(issue)
                else:
                    errors_without_traffic.append(issue)

            # Sort by traffic descending
            errors_with_traffic.sort(key=lambda x: x[1], reverse=True)

            md.append("### 🔴 High Priority (Errors)\n")
            md.append("*Fix these first - they significantly impact SEO*\n")

            # Show high-traffic errors first
            if errors_with_traffic:
                md.append("#### High Traffic Pages\n")
                for issue, clicks in errors_with_traffic:
                    add_issue_with_traffic(issue, "🚨")

            # Then show other errors
            if errors_without_traffic:
                if errors_with_traffic:
                    md.append("#### Other Pages\n")
                for issue in errors_without_traffic:
                    add_issue_with_traffic(issue, "")

            md.append("")

        # Warnings (Medium Priority) - Sort by traffic
        if issues_by_severity[Severity.WARNING]:
            warnings_list = issues_by_severity[Severity.WARNING]
            warnings_with_traffic = []
            warnings_without_traffic = []

            for issue in warnings_list:
                if issue.affected_url:
                    gsc_data = self._match_gsc_to_page(issue.affected_url)
                    if gsc_data and gsc_data.get('clicks', 0) > 0:
                        warnings_with_traffic.append((issue, gsc_data['clicks']))
                    else:
                        warnings_without_traffic.append(issue)
                else:
                    warnings_without_traffic.append(issue)

            warnings_with_traffic.sort(key=lambda x: x[1], reverse=True)

            md.append("### 🟡 Medium Priority (Warnings)\n")
            md.append("*Address these to improve SEO performance*\n")

            if warnings_with_traffic:
                md.append("#### High Traffic Pages\n")
                for issue, clicks in warnings_with_traffic:
                    add_issue_with_traffic(issue, "⚠️")

            if warnings_without_traffic:
                if warnings_with_traffic:
                    md.append("#### Other Pages\n")
                for issue in warnings_without_traffic:
                    add_issue_with_traffic(issue, "")

            md.append("")

        # Notices (Low Priority) - Sort by traffic
        if issues_by_severity[Severity.NOTICE]:
            notices_list = issues_by_severity[Severity.NOTICE]
            notices_with_traffic = []
            notices_without_traffic = []

            for issue in notices_list:
                if issue.affected_url:
                    gsc_data = self._match_gsc_to_page(issue.affected_url)
                    if gsc_data and gsc_data.get('clicks', 0) > 0:
                        notices_with_traffic.append((issue, gsc_data['clicks']))
                    else:
                        notices_without_traffic.append(issue)
                else:
                    notices_without_traffic.append(issue)

            notices_with_traffic.sort(key=lambda x: x[1], reverse=True)

            md.append("### 🔵 Low Priority (Improvements)\n")
            md.append("*Nice-to-have optimizations*\n")

            if notices_with_traffic:
                md.append("#### High Traffic Pages\n")
                for issue, clicks in notices_with_traffic:
                    add_issue_with_traffic(issue, "ℹ️")

            if notices_without_traffic:
                if notices_with_traffic:
                    md.append("#### Other Pages\n")
                for issue in notices_without_traffic:
                    add_issue_with_traffic(issue, "")

            md.append("")

        md.append("---\n")

        # Issue Breakdown by Type
        md.append("## 📊 Issue Breakdown by Type\n")
        for issue_type, type_issues in sorted(issues_by_type.items()):
            count = len(type_issues)
            md.append(f"### {issue_type.replace('_', ' ').title()} ({count})\n")

            # Show all issues
            for issue in type_issues:
                md.append(f"- `{issue.affected_url}`")
                md.append(f"  - {issue.description}")

            md.append("")

        md.append("---\n")

        # Page Inventory
        md.append("## 📄 Page Inventory\n")
        md.append("| URL | Status | Title | Meta Description |\n")
        md.append("|-----|--------|-------|------------------|\n")

        for page in pages[:50]:  # Limit to 50 for readability
            status = page.status_code or "N/A"
            title = (page.title or "Missing")[:50]
            meta = (page.meta_description or "Missing")[:50]
            md.append(f"| {page.url} | {status} | {title} | {meta} |")

        if len(pages) > 50:
            md.append(f"\n*Showing first 50 of {len(pages)} pages*\n")

        md.append("\n---\n")

        # Recommendations
        md.append("## 💡 Recommendations\n")
        md.append("1. Start with **High Priority** items in the to-do list above")
        md.append("2. Focus on fixing errors before warnings")
        md.append("3. Use this markdown file with an LLM to generate specific fix instructions")
        md.append("4. Re-run the audit after fixes to verify improvements")
        md.append("5. Track progress by checking off items in the to-do list\n")

        md.append("---\n")
        md.append(f"*Report generated by {self.business_name}*\n")

        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md))

        print(f"Markdown report exported to: {output_path}")

    def export_html(self, output_path: str = "audit_report.html") -> None:
        """
        Export audit report as styled HTML.
        Opens beautifully in any browser.
        """
        pages = self.db.get_all_pages()
        issues = self.db.get_all_issues()

        # Group issues by severity
        issues_by_severity = defaultdict(list)
        for issue in issues:
            issues_by_severity[issue.severity].append(issue)

        # Count statistics
        total_pages = len(pages)
        total_issues = len(issues)
        errors = len(issues_by_severity[Severity.ERROR])
        warnings = len(issues_by_severity[Severity.WARNING])
        notices = len(issues_by_severity[Severity.NOTICE])

        # Calculate health score (scaled by pages)
        if total_pages > 0:
            # Calculate issue rate per page, weighted by severity
            issue_rate = ((errors * 3) + (warnings * 2) + (notices * 1)) / total_pages
            # Scale to 0-100 (0 issues = 100, higher issue rate = lower score)
            health_score = max(0, min(100, 100 - (issue_rate * 25)))
        else:
            health_score = 0

        # Get domain from first page
        domain = urlparse(pages[0].url).netloc if pages else "Unknown"

        # Get traffic summary
        traffic_summary = self._get_traffic_summary()

        # Get backlinks summary
        backlinks_summary = self._get_backlinks_data(domain)

        # Build HTML
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SEO Report of {domain}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; line-height: 1.6; color: #333; background: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        h1 {{ color: #2c3e50; margin-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 2px solid #3498db; }}
        h3 {{ color: #7f8c8d; margin-top: 20px; margin-bottom: 10px; }}
        h4 {{ color: #95a5a6; margin-top: 15px; margin-bottom: 8px; }}
        .meta {{ color: #7f8c8d; margin-bottom: 30px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
        .stat-card {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; text-align: center; }}
        .stat-card.error {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }}
        .stat-card.warning {{ background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%); color: #333; }}
        .stat-card.notice {{ background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%); color: #333; }}
        .stat-card.traffic {{ background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); color: #333; }}
        .stat-number {{ font-size: 36px; font-weight: bold; }}
        .stat-label {{ font-size: 14px; opacity: 0.9; margin-top: 5px; }}
        .health-score {{ font-size: 48px; font-weight: bold; color: #27ae60; text-align: center; margin: 20px 0; }}
        .health-score.medium {{ color: #f39c12; }}
        .health-score.low {{ color: #e74c3c; }}
        .todo-list {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .todo-item {{ background: white; margin: 10px 0; padding: 15px; border-left: 4px solid #3498db; border-radius: 4px; }}
        .todo-item.error {{ border-left-color: #e74c3c; }}
        .todo-item.warning {{ border-left-color: #f39c12; }}
        .todo-item.notice {{ border-left-color: #3498db; }}
        .todo-item input[type="checkbox"] {{ margin-right: 10px; transform: scale(1.2); }}
        .traffic-info {{ background: #e8f5e9; padding: 10px; margin: 10px 0; border-radius: 4px; font-size: 14px; }}
        .queries {{ margin-left: 20px; font-size: 13px; color: #555; }}
        .opportunity {{ background: #fff3cd; padding: 8px; margin-top: 8px; border-radius: 4px; font-weight: bold; color: #856404; }}
        .badge {{ display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; margin-right: 8px; }}
        .badge.error {{ background: #e74c3c; color: white; }}
        .badge.warning {{ background: #f39c12; color: white; }}
        .badge.notice {{ background: #3498db; color: white; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th {{ background: #34495e; color: white; padding: 12px; text-align: left; }}
        td {{ padding: 12px; border-bottom: 1px solid #ecf0f1; }}
        tr:hover {{ background: #f8f9fa; }}
        code {{ background: #ecf0f1; padding: 2px 6px; border-radius: 3px; font-family: 'Courier New', monospace; }}
        .url {{ color: #3498db; text-decoration: none; }}
        .url:hover {{ text-decoration: underline; }}
        .details {{ color: #7f8c8d; font-size: 14px; margin-top: 5px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 SEO Report of {domain}</h1>
        {'<p class="meta"><strong>Prepared by:</strong> ' + self.prepared_by + '</p>' if self.prepared_by else ''}
        <p class="meta">Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}</p>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-number">{total_pages}</div>
                <div class="stat-label">Pages Crawled</div>
            </div>
            <div class="stat-card error">
                <div class="stat-number">{errors}</div>
                <div class="stat-label">Errors</div>
            </div>
            <div class="stat-card warning">
                <div class="stat-number">{warnings}</div>
                <div class="stat-label">Warnings</div>
            </div>
            <div class="stat-card notice">
                <div class="stat-number">{notices}</div>
                <div class="stat-label">Notices</div>
            </div>
"""

        # Add traffic stats if available
        if traffic_summary:
            html += f"""
            <div class="stat-card traffic">
                <div class="stat-number">{traffic_summary['total_clicks']:,}</div>
                <div class="stat-label">Clicks (GSC)</div>
            </div>
            <div class="stat-card traffic">
                <div class="stat-number">{traffic_summary['total_impressions']:,}</div>
                <div class="stat-label">Impressions (GSC)</div>
            </div>
"""

        # Add backlinks stats if available
        if backlinks_summary:
            html += f"""
            <div class="stat-card traffic">
                <div class="stat-number">{backlinks_summary['total_domains']:,}</div>
                <div class="stat-label">Referring Domains</div>
            </div>
"""

        html += f"""
        </div>

        <div class="health-score {'low' if health_score < 50 else 'medium' if health_score < 80 else ''}">
            SEO Health Score: {health_score:.0f}/100
        </div>

"""

        # Add backlinks section if available
        if backlinks_summary:
            html += f"""
        <h2>🔗 Backlink Profile</h2>
        <p><strong>Data from Common Crawl ({backlinks_summary['graph_date']})</strong></p>
        <p>Average Quality Score: {backlinks_summary['avg_quality']:.2f}/1.0</p>
        <table>
            <thead>
                <tr>
                    <th>Referring Domain</th>
                    <th>Links</th>
                    <th>Quality Score</th>
                </tr>
            </thead>
            <tbody>
"""
            for bl in backlinks_summary['top_backlinks'][:20]:
                html += f"""
                <tr>
                    <td><a href="http://{bl['referring_domain']}" target="_blank" class="url">{bl['referring_domain']}</a></td>
                    <td>{bl['link_count']}</td>
                    <td>{bl['quality_score']:.2f}</td>
                </tr>
"""
            html += """
            </tbody>
        </table>
"""

        html += """

        <h2>🎯 Action Items</h2>
        <div class="todo-list">
"""

        # Helper function to add issue HTML with traffic data
        def add_issue_html(issue, severity_class):
            issue_html = f"""
            <div class="todo-item {severity_class}">
                <input type="checkbox" id="{id(issue)}">
                <label for="{id(issue)}">
                    <strong>{issue.issue_type.replace('_', ' ').title()}</strong>
                    <br><code>{issue.affected_url}</code>
                    <div class="details">{issue.description}</div>
"""

            # Add traffic data if available
            if issue.affected_url:
                gsc_data = self._match_gsc_to_page(issue.affected_url)
                if gsc_data:
                    issue_html += f"""
                    <div class="traffic-info">
                        📈 <strong>Traffic:</strong> {gsc_data['clicks']:,} clicks/month, Position: {gsc_data['position']:.1f}
"""

                    # Show top queries
                    if gsc_data.get('queries'):
                        issue_html += """<div class="queries">🔍 <strong>Top Queries:</strong><ul>"""
                        for q in gsc_data['queries'][:3]:
                            issue_html += f"""<li>"{q['query']}" (Pos {q['position']:.1f}, {q['clicks']} clicks)</li>"""
                        issue_html += """</ul></div>"""

                    issue_html += """</div>"""

                    # Calculate opportunity
                    opportunity = self._calculate_opportunity(gsc_data)
                    if opportunity:
                        issue_html += f"""<div class="opportunity">💰 Opportunity: {opportunity}</div>"""

            if issue.details:
                issue_html += f"""<div class="details">{self._format_details(issue.details)}</div>"""

            issue_html += """
                </label>
            </div>
"""
            return issue_html

        # Add errors (traffic-prioritized)
        if issues_by_severity[Severity.ERROR]:
            errors_list = issues_by_severity[Severity.ERROR]
            errors_with_traffic = []
            errors_without_traffic = []

            for issue in errors_list:
                if issue.affected_url:
                    gsc_data = self._match_gsc_to_page(issue.affected_url)
                    if gsc_data and gsc_data.get('clicks', 0) > 0:
                        errors_with_traffic.append((issue, gsc_data['clicks']))
                    else:
                        errors_without_traffic.append(issue)
                else:
                    errors_without_traffic.append(issue)

            errors_with_traffic.sort(key=lambda x: x[1], reverse=True)

            html += f"<h3>🔴 High Priority ({len(errors_list)})</h3>"

            if errors_with_traffic:
                html += "<h4>High Traffic Pages</h4>"
                for issue, clicks in errors_with_traffic:
                    html += add_issue_html(issue, "error")

            if errors_without_traffic:
                if errors_with_traffic:
                    html += "<h4>Other Pages</h4>"
                for issue in errors_without_traffic:
                    html += add_issue_html(issue, "error")

        # Add warnings (traffic-prioritized)
        if issues_by_severity[Severity.WARNING]:
            warnings_list = issues_by_severity[Severity.WARNING]
            warnings_with_traffic = []
            warnings_without_traffic = []

            for issue in warnings_list:
                if issue.affected_url:
                    gsc_data = self._match_gsc_to_page(issue.affected_url)
                    if gsc_data and gsc_data.get('clicks', 0) > 0:
                        warnings_with_traffic.append((issue, gsc_data['clicks']))
                    else:
                        warnings_without_traffic.append(issue)
                else:
                    warnings_without_traffic.append(issue)

            warnings_with_traffic.sort(key=lambda x: x[1], reverse=True)

            html += f"<h3>🟡 Medium Priority ({len(warnings_list)})</h3>"

            if warnings_with_traffic:
                html += "<h4>High Traffic Pages</h4>"
                for issue, clicks in warnings_with_traffic:
                    html += add_issue_html(issue, "warning")

            if warnings_without_traffic:
                if warnings_with_traffic:
                    html += "<h4>Other Pages</h4>"
                for issue in warnings_without_traffic:
                    html += add_issue_html(issue, "warning")

        # Add notices (traffic-prioritized)
        if issues_by_severity[Severity.NOTICE]:
            notices_list = issues_by_severity[Severity.NOTICE]
            notices_with_traffic = []
            notices_without_traffic = []

            for issue in notices_list:
                if issue.affected_url:
                    gsc_data = self._match_gsc_to_page(issue.affected_url)
                    if gsc_data and gsc_data.get('clicks', 0) > 0:
                        notices_with_traffic.append((issue, gsc_data['clicks']))
                    else:
                        notices_without_traffic.append(issue)
                else:
                    notices_without_traffic.append(issue)

            notices_with_traffic.sort(key=lambda x: x[1], reverse=True)

            html += f"<h3>🔵 Low Priority ({len(notices_list)})</h3>"

            if notices_with_traffic:
                html += "<h4>High Traffic Pages</h4>"
                for issue, clicks in notices_with_traffic:
                    html += add_issue_html(issue, "notice")

            if notices_without_traffic:
                if notices_with_traffic:
                    html += "<h4>Other Pages</h4>"
                for issue in notices_without_traffic:
                    html += add_issue_html(issue, "notice")

        html += """
        </div>

        <h2>📊 Page Summary</h2>
        <table>
            <thead>
                <tr>
                    <th>URL</th>
                    <th>Status</th>
                    <th>Title</th>
                    <th>Issues</th>
                </tr>
            </thead>
            <tbody>
"""

        # Add page rows
        for page in pages[:50]:
            page_issues = [i for i in issues if i.affected_url == page.url]
            issue_count = len(page_issues)
            status_color = "green" if page.status_code and 200 <= page.status_code < 300 else "red"

            html += f"""
                <tr>
                    <td><a href="{page.url}" class="url" target="_blank">{page.url}</a></td>
                    <td style="color: {status_color}; font-weight: bold;">{page.status_code or 'N/A'}</td>
                    <td>{page.title or '<em>Missing</em>'}</td>
                    <td>{issue_count} issue{'s' if issue_count != 1 else ''}</td>
                </tr>
"""

        html += """
            </tbody>
        </table>

        <h2>💡 Next Steps</h2>
        <ol>
            <li>Check off items in the Action Items section as you fix them</li>
            <li>Start with High Priority (Errors) first</li>
            <li>Focus on one issue type at a time for efficiency</li>
            <li>Re-run the audit after fixes to verify improvements</li>
        </ol>

        <p style="margin-top: 40px; text-align: center; color: #7f8c8d; font-size: 14px;">
            Report generated by {self.business_name}
        </p>
    </div>

    <script>
        // Save checkbox state to localStorage
        document.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const key = 'todo_' + e.target.id;
                localStorage.setItem(key, e.target.checked);
            });

            // Restore state
            const key = 'todo_' + checkbox.id;
            const saved = localStorage.getItem(key);
            if (saved === 'true') {
                checkbox.checked = true;
            }
        });
    </script>
</body>
</html>
"""

        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

        print(f"HTML report exported to: {output_path}")

    def _format_details(self, details: dict) -> str:
        """Format issue details for display."""
        if not details:
            return ""

        parts = []
        for key, value in details.items():
            if key in ['other_urls', 'chain']:
                continue  # Skip verbose fields
            parts.append(f"{key}: {value}")

        return ", ".join(parts)

    def export_backlinks_csv(self, domain: str, output_path: str = "audit_backlinks.csv") -> None:
        """Export backlinks as CSV for analysis."""
        backlinks = self.db.get_cc_backlinks(domain, limit=1000)

        if not backlinks:
            print("No backlinks data available to export")
            return

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                "Referring Domain",
                "Link Count",
                "Quality Score",
                "Graph Date"
            ])

            # Data rows
            for bl in backlinks:
                writer.writerow([
                    bl['referring_domain'],
                    bl['link_count'],
                    f"{bl['quality_score']:.2f}",
                    bl['graph_date']
                ])

        print(f"Backlinks CSV exported to: {output_path}")

    def export_all(self, output_dir: str = ".") -> None:
        """Export all data formats to a directory."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Export each format with error handling
        try:
            self.export_json(str(output_path / "audit_report.json"))
        except Exception as e:
            print(f"Error exporting JSON: {e}")

        try:
            self.export_markdown(str(output_path / "audit_report.md"))
        except Exception as e:
            print(f"Error exporting Markdown: {e}")

        try:
            self.export_html(str(output_path / "audit_report.html"))
        except Exception as e:
            print(f"Error exporting HTML: {e}")

        try:
            self.export_issues_csv(str(output_path / "audit_issues.csv"))
        except Exception as e:
            print(f"Error exporting issues CSV: {e}")

        try:
            self.export_pages_csv(str(output_path / "audit_pages.csv"))
        except Exception as e:
            print(f"Error exporting pages CSV: {e}")

        # Export backlinks if available
        try:
            pages = self.db.get_all_pages()
            if pages:
                domain = urlparse(pages[0].url).netloc
                if self.db.has_cc_backlinks(domain):
                    self.export_backlinks_csv(domain, str(output_path / "audit_backlinks.csv"))
        except Exception as e:
            print(f"Error exporting backlinks CSV: {e}")

        print(f"\nAll reports exported to: {output_dir}")
