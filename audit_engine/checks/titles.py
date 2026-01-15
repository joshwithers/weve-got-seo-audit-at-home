"""
Check for missing and duplicate page titles.
"""

from typing import List
from collections import Counter

from .base import BaseCheck
from ..models import Issue, Severity


class TitlesCheck(BaseCheck):
    """Detects missing and duplicate page titles."""

    @property
    def name(self) -> str:
        return "Page Titles"

    @property
    def description(self) -> str:
        return "Finds pages with missing or duplicate title tags"

    def run(self) -> List[Issue]:
        issues = []
        pages = self.db.get_all_pages()

        # Track titles for duplicate detection
        title_urls = {}

        for page in pages:
            # Only check successful pages
            if not page.status_code or page.status_code < 200 or page.status_code >= 300:
                continue

            # Check for missing title
            if not page.title or not page.title.strip():
                issues.append(Issue(
                    issue_type="missing_title",
                    severity=Severity.ERROR,
                    description="Page is missing a title tag",
                    affected_url=page.url
                ))
            else:
                # Check for too short titles
                if len(page.title.strip()) < 10:
                    issues.append(Issue(
                        issue_type="short_title",
                        severity=Severity.WARNING,
                        description=f"Page title is too short ({len(page.title)} characters)",
                        affected_url=page.url,
                        details={"title": page.title}
                    ))

                # Check for too long titles
                if len(page.title.strip()) > 60:
                    issues.append(Issue(
                        issue_type="long_title",
                        severity=Severity.WARNING,
                        description=f"Page title is too long ({len(page.title)} characters, recommended: 50-60)",
                        affected_url=page.url,
                        details={"title": page.title}
                    ))

                # Track for duplicate detection
                title_normalized = page.title.strip().lower()
                if title_normalized not in title_urls:
                    title_urls[title_normalized] = []
                title_urls[title_normalized].append(page.url)

        # Check for duplicate titles
        for title, urls in title_urls.items():
            if len(urls) > 1:
                for url in urls:
                    issues.append(Issue(
                        issue_type="duplicate_title",
                        severity=Severity.WARNING,
                        description=f"Page has a duplicate title (used on {len(urls)} pages)",
                        affected_url=url,
                        details={
                            "title": title,
                            "duplicate_count": len(urls),
                            "other_urls": [u for u in urls if u != url][:5]  # Limit to 5 examples
                        }
                    ))

        return issues
