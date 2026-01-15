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

    def export_json(self, output_path: str = "audit_report.json") -> None:
        """
        Export complete audit report as JSON.
        Includes pages, issues, and summary statistics.
        """
        pages = self.db.get_all_pages()
        issues = self.db.get_all_issues()

        # Get domain from first page
        domain = pages[0].url if pages else "Unknown"

        # Build the report structure
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "report_title": f"SEO Report of {urlparse(domain).netloc}",
            "business_name": self.business_name,
            "prepared_by": self.prepared_by if self.prepared_by else None,
            "summary": {
                "total_pages": len(pages),
                "total_issues": len(issues),
                "errors": sum(1 for i in issues if i.severity.value == "error"),
                "warnings": sum(1 for i in issues if i.severity.value == "warning"),
                "notices": sum(1 for i in issues if i.severity.value == "notice"),
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

            # Header
            writer.writerow([
                "Issue Type",
                "Severity",
                "Description",
                "Affected URL",
                "Details",
                "Created At"
            ])

            # Data rows
            for issue in issues:
                writer.writerow([
                    issue.issue_type,
                    issue.severity.value,
                    issue.description,
                    issue.affected_url or "",
                    json.dumps(issue.details) if issue.details else "",
                    issue.created_at.isoformat() if issue.created_at else ""
                ])

        print(f"Issues CSV exported to: {output_path}")

    def export_pages_csv(self, output_path: str = "audit_pages.csv") -> None:
        """Export pages as CSV for analysis."""
        pages = self.db.get_all_pages()

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Header
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
                "Crawled At"
            ])

            # Data rows
            for page in pages:
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
                    page.crawled_at.isoformat() if page.crawled_at else ""
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

        # Start building markdown
        md = []
        md.append(f"# SEO Report of {domain}\n")
        if self.prepared_by:
            md.append(f"**Prepared by:** {self.prepared_by}\n")
        md.append(f"**Generated:** {datetime.utcnow().strftime('%B %d, %Y at %H:%M UTC')}\n")
        md.append("---\n")

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

        # TO-DO LIST
        md.append("## 🎯 Action Items (To-Do List)\n")
        md.append("*Copy this section to track your fixes*\n")

        # Errors (High Priority)
        if issues_by_severity[Severity.ERROR]:
            md.append("### High Priority (Errors)\n")
            md.append("*Fix these first - they significantly impact SEO*\n")
            for i, issue in enumerate(issues_by_severity[Severity.ERROR], 1):
                md.append(f"- [ ] **{issue.issue_type.replace('_', ' ').title()}**")
                md.append(f"  - Page: `{issue.affected_url}`")
                md.append(f"  - Issue: {issue.description}")
                if issue.details:
                    md.append(f"  - Details: {self._format_details(issue.details)}")
                md.append("")

        # Warnings (Medium Priority)
        if issues_by_severity[Severity.WARNING]:
            md.append("### Medium Priority (Warnings)\n")
            md.append("*Address these to improve SEO performance*\n")
            for i, issue in enumerate(issues_by_severity[Severity.WARNING], 1):
                md.append(f"- [ ] **{issue.issue_type.replace('_', ' ').title()}**")
                md.append(f"  - Page: `{issue.affected_url}`")
                md.append(f"  - Issue: {issue.description}")
                if issue.details:
                    md.append(f"  - Details: {self._format_details(issue.details)}")
                md.append("")

        # Notices (Low Priority)
        if issues_by_severity[Severity.NOTICE]:
            md.append("### Low Priority (Improvements)\n")
            md.append("*Nice-to-have optimizations*\n")
            for i, issue in enumerate(issues_by_severity[Severity.NOTICE], 1):
                md.append(f"- [ ] **{issue.issue_type.replace('_', ' ').title()}**")
                md.append(f"  - Page: `{issue.affected_url}`")
                md.append(f"  - Issue: {issue.description}")
                md.append("")

        md.append("---\n")

        # Issue Breakdown by Type
        md.append("## 📊 Issue Breakdown by Type\n")
        for issue_type, type_issues in sorted(issues_by_type.items()):
            count = len(type_issues)
            md.append(f"### {issue_type.replace('_', ' ').title()} ({count})\n")

            # Show up to 5 examples
            for issue in type_issues[:5]:
                md.append(f"- `{issue.affected_url}`")
                md.append(f"  - {issue.description}")

            if len(type_issues) > 5:
                md.append(f"  - *...and {len(type_issues) - 5} more*")

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
        .meta {{ color: #7f8c8d; margin-bottom: 30px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
        .stat-card {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; text-align: center; }}
        .stat-card.error {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }}
        .stat-card.warning {{ background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%); color: #333; }}
        .stat-card.notice {{ background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%); color: #333; }}
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
        <p class="meta">Generated: {datetime.utcnow().strftime('%B %d, %Y at %H:%M UTC')}</p>

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
        </div>

        <div class="health-score {'low' if health_score < 50 else 'medium' if health_score < 80 else ''}">
            SEO Health Score: {health_score:.0f}/100
        </div>

        <h2>🎯 Action Items</h2>
        <div class="todo-list">
"""

        # Add errors
        if issues_by_severity[Severity.ERROR]:
            html += f"<h3>🔴 High Priority ({len(issues_by_severity[Severity.ERROR])})</h3>"
            for issue in issues_by_severity[Severity.ERROR]:
                html += f"""
            <div class="todo-item error">
                <input type="checkbox" id="{id(issue)}">
                <label for="{id(issue)}">
                    <strong>{issue.issue_type.replace('_', ' ').title()}</strong>
                    <br><code>{issue.affected_url}</code>
                    <div class="details">{issue.description}</div>
                    {f'<div class="details">{self._format_details(issue.details)}</div>' if issue.details else ''}
                </label>
            </div>
"""

        # Add warnings
        if issues_by_severity[Severity.WARNING]:
            html += f"<h3>🟡 Medium Priority ({len(issues_by_severity[Severity.WARNING])})</h3>"
            for issue in issues_by_severity[Severity.WARNING]:
                html += f"""
            <div class="todo-item warning">
                <input type="checkbox" id="{id(issue)}">
                <label for="{id(issue)}">
                    <strong>{issue.issue_type.replace('_', ' ').title()}</strong>
                    <br><code>{issue.affected_url}</code>
                    <div class="details">{issue.description}</div>
                </label>
            </div>
"""

        # Add notices
        if issues_by_severity[Severity.NOTICE]:
            html += f"<h3>🔵 Low Priority ({len(issues_by_severity[Severity.NOTICE])})</h3>"
            for issue in issues_by_severity[Severity.NOTICE]:
                html += f"""
            <div class="todo-item notice">
                <input type="checkbox" id="{id(issue)}">
                <label for="{id(issue)}">
                    <strong>{issue.issue_type.replace('_', ' ').title()}</strong>
                    <br><code>{issue.affected_url}</code>
                    <div class="details">{issue.description}</div>
                </label>
            </div>
"""

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

    def export_all(self, output_dir: str = ".") -> None:
        """Export all data formats to a directory."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        self.export_json(str(output_path / "audit_report.json"))
        self.export_markdown(str(output_path / "audit_report.md"))
        self.export_html(str(output_path / "audit_report.html"))
        self.export_issues_csv(str(output_path / "audit_issues.csv"))
        self.export_pages_csv(str(output_path / "audit_pages.csv"))

        print(f"\nAll reports exported to: {output_dir}")
