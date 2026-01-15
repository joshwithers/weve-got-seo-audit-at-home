"""
Check for redirect chains and redirect issues.
"""

from typing import List, Set

from .base import BaseCheck
from ..models import Issue, Severity


class RedirectsCheck(BaseCheck):
    """Detects redirect chains and problematic redirects."""

    @property
    def name(self) -> str:
        return "Redirects"

    @property
    def description(self) -> str:
        return "Finds redirect chains and pages that redirect"

    def run(self) -> List[Issue]:
        issues = []
        pages = self.db.get_all_pages()

        # Build a map of redirects
        redirect_map = {}
        for page in pages:
            if page.redirect_to and page.redirect_to != page.url:
                redirect_map[page.url] = page.redirect_to

        # Check each page with a redirect
        for page in pages:
            if not page.redirect_to or page.redirect_to == page.url:
                continue

            # Detect redirect chains
            chain = [page.url]
            current = page.redirect_to
            visited = {page.url}

            # Follow the redirect chain
            while current in redirect_map and current not in visited:
                chain.append(current)
                visited.add(current)
                current = redirect_map[current]

            # Add final destination if not a redirect
            if current not in redirect_map:
                chain.append(current)

            # Report if chain is longer than 1 redirect
            if len(chain) > 2:
                issues.append(Issue(
                    issue_type="redirect_chain",
                    severity=Severity.WARNING,
                    description=f"Page has a redirect chain of {len(chain) - 1} redirect(s)",
                    affected_url=page.url,
                    details={
                        "chain": chain,
                        "chain_length": len(chain) - 1
                    }
                ))
            else:
                # Single redirect - just a notice
                issues.append(Issue(
                    issue_type="redirect",
                    severity=Severity.NOTICE,
                    description=f"Page redirects to another URL",
                    affected_url=page.url,
                    details={
                        "redirect_to": page.redirect_to
                    }
                ))

            # Check for redirect loops
            if current in visited and current != chain[-1]:
                issues.append(Issue(
                    issue_type="redirect_loop",
                    severity=Severity.ERROR,
                    description=f"Page is part of a redirect loop",
                    affected_url=page.url,
                    details={
                        "chain": chain
                    }
                ))

        return issues
