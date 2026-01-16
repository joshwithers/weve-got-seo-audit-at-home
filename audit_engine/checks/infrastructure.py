"""
Infrastructure and security checks for SEO audit.

Checks for:
- Robots.txt crawl permissions
- AI/LLM crawler permissions
- Sitemap availability
- SSL certificate
- Email deliverability (SPF/DMARC)
"""

import ssl
import socket
import dns.resolver
from urllib.parse import urlparse
from datetime import datetime
from typing import List

import requests

from ..models import Issue, Severity
from .base import BaseCheck


class InfrastructureCheck(BaseCheck):
    """Check infrastructure and security settings."""

    @property
    def name(self) -> str:
        return "Infrastructure & Security"

    @property
    def description(self) -> str:
        return "Checks SSL, robots.txt, sitemap, and email deliverability"

    def run(self) -> List[Issue]:
        """Run infrastructure checks."""
        issues = []

        # Get the seed URL from crawl metadata
        with self.db._connect() as conn:
            row = conn.execute(
                "SELECT seed_url FROM crawl_meta ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if not row:
                return issues
            seed_url = row['seed_url']

        parsed = urlparse(seed_url)
        domain = parsed.netloc
        scheme = parsed.scheme

        # Check SSL Certificate
        if scheme == 'https':
            ssl_issue = self._check_ssl_certificate(domain)
            if ssl_issue:
                issues.append(ssl_issue)
        else:
            issues.append(Issue(
                issue_type="no_ssl",
                severity=Severity.ERROR,
                description="Site not using HTTPS",
                affected_url=seed_url,
                details={"message": "HTTPS is essential for SEO and security"}
            ))

        # Check robots.txt
        robots_issues = self._check_robots_txt(seed_url, domain)
        issues.extend(robots_issues)

        # Check sitemap
        sitemap_issue = self._check_sitemap(seed_url)
        if sitemap_issue:
            issues.append(sitemap_issue)

        # Check email deliverability (SPF/DMARC)
        email_issues = self._check_email_records(domain)
        issues.extend(email_issues)

        return issues

    def _check_ssl_certificate(self, domain: str) -> Issue:
        """Check SSL certificate validity and expiry."""
        try:
            context = ssl.create_default_context()
            with socket.create_connection((domain, 443), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert()

                    # Check expiry
                    not_after = cert.get('notAfter')
                    if not_after:
                        expiry_date = datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z')
                        days_until_expiry = (expiry_date - datetime.now()).days

                        if days_until_expiry < 0:
                            return Issue(
                                issue_type="ssl_expired",
                                severity=Severity.ERROR,
                                description="SSL certificate has expired",
                                affected_url=f"https://{domain}",
                                details={
                                    "expired_date": not_after,
                                    "days_expired": abs(days_until_expiry)
                                }
                            )
                        elif days_until_expiry < 30:
                            return Issue(
                                issue_type="ssl_expiring_soon",
                                severity=Severity.WARNING,
                                description=f"SSL certificate expires in {days_until_expiry} days",
                                affected_url=f"https://{domain}",
                                details={
                                    "expiry_date": not_after,
                                    "days_remaining": days_until_expiry
                                }
                            )
            return None
        except Exception as e:
            return Issue(
                issue_type="ssl_check_failed",
                severity=Severity.WARNING,
                description="Unable to verify SSL certificate",
                affected_url=f"https://{domain}",
                details={"error": str(e)}
            )

    def _check_robots_txt(self, seed_url: str, domain: str) -> List[Issue]:
        """Check robots.txt for crawl permissions and AI bot settings."""
        issues = []

        parsed = urlparse(seed_url)
        robots_url = f"{parsed.scheme}://{domain}/robots.txt"

        try:
            response = requests.get(robots_url, timeout=5)

            if response.status_code == 404:
                issues.append(Issue(
                    issue_type="no_robots_txt",
                    severity=Severity.NOTICE,
                    description="No robots.txt file found",
                    affected_url=robots_url,
                    details={"message": "Consider adding robots.txt for better crawler control"}
                ))
                return issues

            if response.status_code != 200:
                issues.append(Issue(
                    issue_type="robots_txt_error",
                    severity=Severity.WARNING,
                    description=f"robots.txt returned status {response.status_code}",
                    affected_url=robots_url
                ))
                return issues

            robots_content = response.text.lower()

            # Check if site blocks all crawlers
            if 'user-agent: *' in robots_content and 'disallow: /' in robots_content:
                # Check if it's right after user-agent: *
                lines = robots_content.split('\n')
                for i, line in enumerate(lines):
                    if 'user-agent: *' in line:
                        # Check next non-empty line
                        for j in range(i + 1, len(lines)):
                            next_line = lines[j].strip()
                            if next_line and not next_line.startswith('#'):
                                if 'disallow: /' == next_line:
                                    issues.append(Issue(
                                        issue_type="robots_blocks_all",
                                        severity=Severity.ERROR,
                                        description="robots.txt blocks all crawlers from entire site",
                                        affected_url=robots_url,
                                        details={"message": "This prevents search engines from indexing your site"}
                                    ))
                                break

            # Check AI/LLM crawler permissions
            ai_bots = {
                'gptbot': 'OpenAI (ChatGPT)',
                'chatgpt-user': 'OpenAI (ChatGPT browsing)',
                'claude-web': 'Anthropic (Claude)',
                'anthropic-ai': 'Anthropic (Claude)',
                'googlebot-ai': 'Google (Gemini)',
                'bingbot-ai': 'Microsoft (Copilot)',
                'perplexitybot': 'Perplexity',
                'cohere-ai': 'Cohere',
                'omgilibot': 'Webz.io',
                'facebookbot': 'Meta AI',
                'diffbot': 'Diffbot',
                'ccbot': 'Common Crawl'
            }

            blocked_ai_bots = []
            allowed_ai_bots = []

            for bot, name in ai_bots.items():
                if f'user-agent: {bot}' in robots_content:
                    # Find what comes after this user-agent
                    lines = robots_content.split('\n')
                    for i, line in enumerate(lines):
                        if f'user-agent: {bot}' in line:
                            # Check subsequent lines
                            for j in range(i + 1, len(lines)):
                                next_line = lines[j].strip()
                                if next_line.startswith('user-agent:'):
                                    break
                                if 'disallow: /' in next_line:
                                    blocked_ai_bots.append(name)
                                    break
                                elif 'allow: /' in next_line:
                                    allowed_ai_bots.append(name)
                                    break

            if blocked_ai_bots:
                issues.append(Issue(
                    issue_type="ai_crawlers_blocked",
                    severity=Severity.NOTICE,
                    description=f"AI crawlers blocked: {', '.join(blocked_ai_bots)}",
                    affected_url=robots_url,
                    details={
                        "blocked_bots": blocked_ai_bots,
                        "message": "These AI services cannot use your content for training/responses"
                    }
                ))

            if allowed_ai_bots:
                issues.append(Issue(
                    issue_type="ai_crawlers_allowed",
                    severity=Severity.NOTICE,
                    description=f"AI crawlers explicitly allowed: {', '.join(allowed_ai_bots)}",
                    affected_url=robots_url,
                    details={"allowed_bots": allowed_ai_bots}
                ))

        except requests.RequestException as e:
            issues.append(Issue(
                issue_type="robots_txt_fetch_error",
                severity=Severity.WARNING,
                description="Could not fetch robots.txt",
                affected_url=robots_url,
                details={"error": str(e)}
            ))

        return issues

    def _check_sitemap(self, seed_url: str) -> Issue:
        """Check for sitemap.xml availability."""
        parsed = urlparse(seed_url)
        domain = parsed.netloc

        # Try common sitemap locations
        sitemap_urls = [
            f"{parsed.scheme}://{domain}/sitemap.xml",
            f"{parsed.scheme}://{domain}/sitemap_index.xml",
            f"{parsed.scheme}://{domain}/sitemap-index.xml",
        ]

        # Also check robots.txt for sitemap declaration
        robots_url = f"{parsed.scheme}://{domain}/robots.txt"
        try:
            response = requests.get(robots_url, timeout=5)
            if response.status_code == 200:
                for line in response.text.split('\n'):
                    if line.lower().startswith('sitemap:'):
                        sitemap_url = line.split(':', 1)[1].strip()
                        if sitemap_url not in sitemap_urls:
                            sitemap_urls.insert(0, sitemap_url)
        except:
            pass

        # Test each sitemap URL
        for sitemap_url in sitemap_urls:
            try:
                response = requests.head(sitemap_url, timeout=5, allow_redirects=True)
                if response.status_code == 200:
                    # Sitemap found!
                    return None
            except:
                continue

        # No sitemap found
        return Issue(
            issue_type="no_sitemap",
            severity=Severity.WARNING,
            description="No sitemap.xml found",
            affected_url=f"{parsed.scheme}://{domain}/sitemap.xml",
            details={
                "message": "Sitemaps help search engines discover your pages",
                "checked_urls": sitemap_urls
            }
        )

    def _check_email_records(self, domain: str) -> List[Issue]:
        """Check SPF and DMARC email authentication records."""
        issues = []

        # Check SPF
        try:
            answers = dns.resolver.resolve(domain, 'TXT')
            spf_found = False
            for rdata in answers:
                txt_string = str(rdata).strip('"')
                if txt_string.startswith('v=spf1'):
                    spf_found = True
                    # Basic SPF validation
                    if txt_string.endswith('-all'):
                        # Strict SPF - good
                        pass
                    elif txt_string.endswith('~all'):
                        # Soft fail - okay
                        pass
                    elif txt_string.endswith('+all'):
                        # Dangerous - allows anyone
                        issues.append(Issue(
                            issue_type="spf_too_permissive",
                            severity=Severity.WARNING,
                            description="SPF record uses +all (allows any server)",
                            affected_url=f"DNS: {domain}",
                            details={
                                "spf_record": txt_string,
                                "message": "This makes email spoofing easier"
                            }
                        ))
                    break

            if not spf_found:
                issues.append(Issue(
                    issue_type="no_spf",
                    severity=Severity.WARNING,
                    description="No SPF record found",
                    affected_url=f"DNS: {domain}",
                    details={"message": "SPF helps prevent email spoofing"}
                ))
        except dns.resolver.NXDOMAIN:
            issues.append(Issue(
                issue_type="domain_dns_error",
                severity=Severity.ERROR,
                description="Domain does not exist in DNS",
                affected_url=f"DNS: {domain}"
            ))
        except dns.resolver.NoAnswer:
            issues.append(Issue(
                issue_type="no_spf",
                severity=Severity.WARNING,
                description="No SPF record found",
                affected_url=f"DNS: {domain}",
                details={"message": "SPF helps prevent email spoofing"}
            ))
        except Exception as e:
            # Skip DNS errors silently - might not have email
            pass

        # Check DMARC
        try:
            dmarc_domain = f"_dmarc.{domain}"
            answers = dns.resolver.resolve(dmarc_domain, 'TXT')
            dmarc_found = False
            for rdata in answers:
                txt_string = str(rdata).strip('"')
                if txt_string.startswith('v=DMARC1'):
                    dmarc_found = True
                    # Check policy
                    if 'p=none' in txt_string:
                        issues.append(Issue(
                            issue_type="dmarc_policy_none",
                            severity=Severity.NOTICE,
                            description="DMARC policy is set to 'none' (monitoring only)",
                            affected_url=f"DNS: {dmarc_domain}",
                            details={
                                "dmarc_record": txt_string,
                                "message": "Consider upgrading to 'quarantine' or 'reject'"
                            }
                        ))
                    break

            if not dmarc_found:
                issues.append(Issue(
                    issue_type="no_dmarc",
                    severity=Severity.WARNING,
                    description="No DMARC record found",
                    affected_url=f"DNS: _dmarc.{domain}",
                    details={"message": "DMARC improves email deliverability and security"}
                ))
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            issues.append(Issue(
                issue_type="no_dmarc",
                severity=Severity.WARNING,
                description="No DMARC record found",
                affected_url=f"DNS: _dmarc.{domain}",
                details={"message": "DMARC improves email deliverability and security"}
            ))
        except Exception:
            # Skip DNS errors silently
            pass

        return issues
