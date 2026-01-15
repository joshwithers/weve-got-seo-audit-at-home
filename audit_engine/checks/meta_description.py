"""
Check for missing and problematic meta descriptions.
"""

from typing import List

from .base import BaseCheck
from ..models import Issue, Severity


class MetaDescriptionCheck(BaseCheck):
    """Detects missing and problematic meta descriptions."""

    @property
    def name(self) -> str:
        return "Meta Descriptions"

    @property
    def description(self) -> str:
        return "Finds pages with missing or problematic meta descriptions"

    def run(self) -> List[Issue]:
        issues = []
        pages = self.db.get_all_pages()

        # Track descriptions for duplicate detection
        desc_urls = {}

        for page in pages:
            # Only check successful pages
            if not page.status_code or page.status_code < 200 or page.status_code >= 300:
                continue

            # Check for missing meta description
            if not page.meta_description or not page.meta_description.strip():
                issues.append(Issue(
                    issue_type="missing_meta_description",
                    severity=Severity.WARNING,
                    description="Page is missing a meta description",
                    affected_url=page.url
                ))
            else:
                desc_length = len(page.meta_description.strip())

                # Check for too short descriptions
                if desc_length < 50:
                    issues.append(Issue(
                        issue_type="short_meta_description",
                        severity=Severity.NOTICE,
                        description=f"Meta description is too short ({desc_length} characters, recommended: 120-160)",
                        affected_url=page.url,
                        details={"meta_description": page.meta_description}
                    ))

                # Check for too long descriptions
                if desc_length > 160:
                    issues.append(Issue(
                        issue_type="long_meta_description",
                        severity=Severity.NOTICE,
                        description=f"Meta description is too long ({desc_length} characters, recommended: 120-160)",
                        affected_url=page.url,
                        details={"meta_description": page.meta_description}
                    ))

                # Track for duplicate detection
                desc_normalized = page.meta_description.strip().lower()
                if desc_normalized not in desc_urls:
                    desc_urls[desc_normalized] = []
                desc_urls[desc_normalized].append(page.url)

        # Check for duplicate meta descriptions
        for desc, urls in desc_urls.items():
            if len(urls) > 1:
                for url in urls:
                    issues.append(Issue(
                        issue_type="duplicate_meta_description",
                        severity=Severity.WARNING,
                        description=f"Page has a duplicate meta description (used on {len(urls)} pages)",
                        affected_url=url,
                        details={
                            "meta_description": desc,
                            "duplicate_count": len(urls),
                            "other_urls": [u for u in urls if u != url][:5]
                        }
                    ))

        return issues
