"""
Check for heading structure issues (multiple H1s, missing H1s).
"""

from typing import List

from .base import BaseCheck
from ..models import Issue, Severity


class HeadingsCheck(BaseCheck):
    """Detects heading structure issues."""

    @property
    def name(self) -> str:
        return "Headings Structure"

    @property
    def description(self) -> str:
        return "Finds pages with multiple or missing H1 tags"

    def run(self) -> List[Issue]:
        issues = []
        pages = self.db.get_all_pages()

        for page in pages:
            # Only check successful pages
            if not page.status_code or page.status_code < 200 or page.status_code >= 300:
                continue

            # Check for missing H1
            if page.h1_count == 0:
                issues.append(Issue(
                    issue_type="missing_h1",
                    severity=Severity.WARNING,
                    description="Page is missing an H1 tag",
                    affected_url=page.url
                ))

            # Check for multiple H1s
            elif page.h1_count > 1:
                issues.append(Issue(
                    issue_type="multiple_h1",
                    severity=Severity.WARNING,
                    description=f"Page has {page.h1_count} H1 tags (recommended: 1)",
                    affected_url=page.url,
                    details={
                        "h1_count": page.h1_count,
                        "h1_text": page.h1_text
                    }
                ))

            # Check for empty H1
            elif page.h1_text and not page.h1_text.strip():
                issues.append(Issue(
                    issue_type="empty_h1",
                    severity=Severity.WARNING,
                    description="Page has an empty H1 tag",
                    affected_url=page.url
                ))

        return issues
