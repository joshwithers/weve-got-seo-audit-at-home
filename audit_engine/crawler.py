"""
Core crawling engine for website discovery and data extraction.
"""

import hashlib
import time
from collections import deque
from datetime import datetime
from typing import Set, Optional, List, Tuple
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from .models import Page, Link, CrawlConfig, LinkType
from .database import Database


class Crawler:
    """Website crawler that discovers and extracts page data."""

    def __init__(self, config: CrawlConfig, database: Database):
        self.config = config
        self.db = database
        self.visited: Set[str] = set()
        self.queue: deque = deque()
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': config.user_agent})
        self.robots_parser: Optional[RobotFileParser] = None

    def crawl(self, seed_url: str) -> None:
        """
        Crawl a website starting from the seed URL.
        Uses breadth-first search with depth tracking.
        """
        # Normalize seed URL
        seed_url = self._normalize_url(seed_url)
        base_domain = self._get_domain(seed_url)

        # Initialize robots.txt parser
        if self.config.respect_robots_txt:
            self.robots_parser = self._init_robots_parser(seed_url)

        # Start crawl
        self.queue.append((seed_url, 0))  # (url, depth)
        pages_crawled = 0

        while self.queue and pages_crawled < self.config.max_pages:
            url, depth = self.queue.popleft()

            # Skip if already visited or depth exceeded
            if url in self.visited or depth > self.config.max_depth:
                continue

            # Skip excluded file extensions
            if self._should_exclude_url(url):
                print(f"Skipping {url} (excluded file type)")
                continue

            # Check robots.txt
            if not self._can_fetch(url):
                print(f"Skipping {url} (disallowed by robots.txt)")
                continue

            # Crawl the page
            page = self._fetch_page(url, depth)
            if page:
                self.db.save_page(page)
                self.visited.add(url)
                pages_crawled += 1

                print(f"[{pages_crawled}] Crawled: {url} (status: {page.status_code}, depth: {depth})")

                # Extract and queue internal links if page is successful
                if page.status_code and 200 <= page.status_code < 300:
                    links = self._extract_links(url, page, base_domain)

                    # Save links to database
                    for link in links:
                        self.db.save_link(link)

                        # Queue internal links for crawling
                        if link.link_type == LinkType.INTERNAL and depth < self.config.max_depth:
                            self.queue.append((link.target_url, depth + 1))

                # Rate limiting
                time.sleep(self.config.delay_between_requests)

        # Print crawl completion summary
        print(f"\nCrawled {pages_crawled} pages")
        if pages_crawled >= self.config.max_pages:
            print(f"  Stopped: Reached max pages limit ({self.config.max_pages})")
            print(f"  Tip: Use --max-pages to crawl more pages")
        if not self.queue:
            print(f"  All reachable pages within depth {self.config.max_depth} have been crawled")
            print(f"  Tip: Use --depth to crawl deeper (current: {self.config.max_depth})")

    def _fetch_page(self, url: str, depth: int) -> Optional[Page]:
        """Fetch a page and extract SEO data."""
        try:
            response = self.session.get(
                url,
                timeout=self.config.timeout,
                allow_redirects=self.config.follow_redirects
            )

            page = Page(
                url=url,
                status_code=response.status_code,
                depth=depth,
                crawled_at=datetime.now()
            )

            # Handle redirects
            if response.history:
                page.redirect_to = response.url

            # Parse HTML only for successful responses
            if 200 <= response.status_code < 300 and 'text/html' in response.headers.get('Content-Type', ''):
                soup = BeautifulSoup(response.content, 'html.parser')
                self._extract_seo_data(page, soup)

                # Generate content hash for deduplication detection
                page.content_hash = hashlib.md5(response.content).hexdigest()

            return page

        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            # Still create a page record with error status
            return Page(
                url=url,
                status_code=None,
                depth=depth,
                crawled_at=datetime.now()
            )

    def _extract_seo_data(self, page: Page, soup: BeautifulSoup) -> None:
        """Extract SEO-relevant data from HTML."""

        # Title
        title_tag = soup.find('title')
        page.title = title_tag.get_text().strip() if title_tag else None

        # Meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        page.meta_description = meta_desc.get('content', '').strip() if meta_desc else None

        # Canonical
        canonical = soup.find('link', attrs={'rel': 'canonical'})
        page.canonical = canonical.get('href', '').strip() if canonical else None

        # Robots meta
        robots_meta = soup.find('meta', attrs={'name': 'robots'})
        page.robots_meta = robots_meta.get('content', '').strip() if robots_meta else None

        # H1 tags
        h1_tags = soup.find_all('h1')
        page.h1_count = len(h1_tags)
        page.h1_text = ' | '.join([h1.get_text().strip() for h1 in h1_tags]) if h1_tags else None

    def _extract_links(self, source_url: str, page: Page, base_domain: str) -> List[Link]:
        """Extract all links from a page."""
        links = []

        try:
            response = self.session.get(source_url, timeout=self.config.timeout)
            soup = BeautifulSoup(response.content, 'html.parser')

            for anchor in soup.find_all('a', href=True):
                href = anchor.get('href', '').strip()
                if not href or href.startswith('#') or href.startswith('mailto:') or href.startswith('tel:'):
                    continue

                # Resolve relative URLs
                target_url = urljoin(source_url, href)
                target_url = self._normalize_url(target_url)

                # Determine if internal or external
                link_type = LinkType.INTERNAL if self._get_domain(target_url) == base_domain else LinkType.EXTERNAL

                link = Link(
                    source_url=source_url,
                    target_url=target_url,
                    link_text=anchor.get_text().strip()[:200],  # Limit length
                    link_type=link_type,
                    is_broken=False  # Will be checked by audit
                )
                links.append(link)

        except Exception as e:
            print(f"Error extracting links from {source_url}: {e}")

        return links

    def _normalize_url(self, url: str) -> str:
        """
        Normalize URL for consistency.
        - Remove fragments
        - Lowercase scheme and domain
        - Remove default ports
        - Normalize trailing slashes (keep for root, remove for others)
        """
        parsed = urlparse(url)

        # Normalize path: remove trailing slash except for root path
        path = parsed.path
        if path != '/' and path.endswith('/'):
            path = path.rstrip('/')
        elif not path:
            path = '/'

        # Remove fragment
        normalized = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            parsed.params,
            parsed.query,
            ''  # No fragment
        ))

        return normalized

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        return urlparse(url).netloc.lower()

    def _init_robots_parser(self, seed_url: str) -> Optional[RobotFileParser]:
        """Initialize robots.txt parser for the domain."""
        try:
            parsed = urlparse(seed_url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

            parser = RobotFileParser()
            parser.set_url(robots_url)
            parser.read()

            return parser
        except Exception as e:
            print(f"Could not read robots.txt: {e}")
            return None

    def _should_exclude_url(self, url: str) -> bool:
        """Check if URL should be excluded based on file extension."""
        parsed = urlparse(url)
        path = parsed.path.lower()

        for ext in self.config.exclude_extensions:
            if path.endswith(ext.lower()):
                return True

        return False

    def _can_fetch(self, url: str) -> bool:
        """Check if URL can be fetched according to robots.txt."""
        if not self.config.respect_robots_txt or not self.robots_parser:
            return True

        try:
            return self.robots_parser.can_fetch(self.config.user_agent, url)
        except Exception:
            # If there's an error checking robots.txt, allow the fetch
            return True
