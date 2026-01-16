"""
Check for broken links (404s and unreachable URLs).
"""

from typing import List

from .base import BaseCheck
from ..models import Issue, Severity, LinkType


class BrokenLinksCheck(BaseCheck):
    """Detects broken internal and external links."""

    @property
    def name(self) -> str:
        return "Broken Links"

    @property
    def description(self) -> str:
        return "Finds links pointing to non-existent pages (404s) or unreachable URLs"

    def run(self) -> List[Issue]:
        issues = []
        pages = self.db.get_all_pages()
        links = self.db.get_all_links()

        # Create a set of crawled URLs with their status codes
        url_status = {page.url: page.status_code for page in pages}

        # Files to ignore (utility files not meant for search engines)
        ignored_extensions = ['.xml', '.txt', '.json', 'rss.xml', 'llms.txt', 'robots.txt', 'sitemap.xml']

        # Check each link
        for link in links:
            # Skip links to ignored files
            target_lower = link.target_url.lower()
            if any(target_lower.endswith(ext) for ext in ignored_extensions):
                continue

            target_status = url_status.get(link.target_url)

            # Only check internal links or external links we've crawled
            if link.link_type == LinkType.INTERNAL:
                if target_status is None:
                    # Internal link not found in crawl (possibly excluded by depth/robots.txt)
                    issues.append(Issue(
                        issue_type="broken_link",
                        severity=Severity.WARNING,
                        description=f"Internal link points to uncrawled URL",
                        affected_url=link.source_url,
                        details={
                            "target_url": link.target_url,
                            "link_text": link.link_text
                        }
                    ))
                elif target_status == 404:
                    # Internal link points to 404
                    issues.append(Issue(
                        issue_type="broken_link",
                        severity=Severity.ERROR,
                        description=f"Internal link points to 404 page",
                        affected_url=link.source_url,
                        details={
                            "target_url": link.target_url,
                            "link_text": link.link_text,
                            "status_code": target_status
                        }
                    ))
                elif target_status and target_status >= 400:
                    # Internal link points to error page
                    issues.append(Issue(
                        issue_type="broken_link",
                        severity=Severity.ERROR,
                        description=f"Internal link points to error page ({target_status})",
                        affected_url=link.source_url,
                        details={
                            "target_url": link.target_url,
                            "link_text": link.link_text,
                            "status_code": target_status
                        }
                    ))

        return issues
