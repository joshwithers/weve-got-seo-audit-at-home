"""
Common Crawl backlinks integration for domain authority analysis.

This module provides functionality to query Common Crawl's hyperlinkgraph
dataset to discover backlinks to a target domain, with quality filtering
to remove spam and low-quality referrers.
"""

import gzip
import json
import math
import pickle
import re
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

# Constants
CC_S3_BASE = "s3://commoncrawl/projects/hyperlinkgraph/"
CC_INDEX_URL = "https://data.commoncrawl.org/projects/hyperlinkgraph/"
CACHE_DIR = Path.home() / '.seo_audit' / 'cc_cache'
GRAPH_METADATA_FILE = CACHE_DIR / 'graph_metadata.json'

# Quality thresholds
MIN_LINK_COUNT = 2  # Minimum links from same domain
SPAM_TLDS = ['.xyz', '.top', '.work', '.click', '.link', '.loan',
             '.download', '.stream', '.gq', '.tk', '.ml', '.ga', '.cf']
SPAM_KEYWORDS = ['casino', 'porn', 'viagra', 'lottery', 'pharma',
                 'dating', 'pills', 'cryptocurrency']

DEFAULT_SPAM_CONFIG = {
    'spam_tlds': SPAM_TLDS,
    'spam_keywords': SPAM_KEYWORDS,
    'trusted_tlds': ['.edu', '.gov', '.org'],
    'min_link_count': MIN_LINK_COUNT,
    'min_quality_score': 0.3
}


class CCClient:
    """Common Crawl Hyperlinkgraph client for backlink discovery."""

    def __init__(self):
        self.current_graph = None  # Format: cc-main-YYYY-mmm-mmm-mmm
        self.vertex_index = {}  # Cache: {reversed_domain -> vertex_id}
        self._ensure_cache_dir()
        self._load_spam_config()

    def _ensure_cache_dir(self):
        """Create cache directory if needed."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _load_spam_config(self):
        """Load spam filter configuration."""
        config_file = CACHE_DIR / 'spam_filters.json'

        if config_file.exists():
            with open(config_file, 'r') as f:
                self.spam_config = json.load(f)
        else:
            # Create default config
            self.spam_config = DEFAULT_SPAM_CONFIG
            with open(config_file, 'w') as f:
                json.dump(DEFAULT_SPAM_CONFIG, f, indent=2)

    def test_connection(self) -> bool:
        """
        Test AWS CLI access to Common Crawl S3.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Test: List hyperlinkgraph directory
            result = subprocess.run(
                ['aws', 's3', 'ls', '--no-sign-request', CC_S3_BASE],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except FileNotFoundError:
            # AWS CLI not installed
            return False
        except Exception:
            return False

    def check_for_updates(self, force: bool = False) -> Optional[str]:
        """
        Check for new graph releases.

        Args:
            force: Force check even if recent check exists

        Returns:
            New graph ID if available, None otherwise
        """
        # Get latest graph from index
        latest_graph = self._get_latest_graph_id()

        if not latest_graph:
            return None

        # Check if we already have this graph
        if GRAPH_METADATA_FILE.exists():
            with open(GRAPH_METADATA_FILE, 'r') as f:
                metadata = json.load(f)
                cached_graph = metadata.get('graph_id')

            if cached_graph == latest_graph:
                # Already have latest
                self.current_graph = latest_graph
                return None

        # New graph available
        # Update metadata
        with open(GRAPH_METADATA_FILE, 'w') as f:
            json.dump({
                'graph_id': latest_graph,
                'checked_at': datetime.utcnow().isoformat()
            }, f, indent=2)

        self.current_graph = latest_graph
        return latest_graph

    def _get_latest_graph_id(self) -> Optional[str]:
        """
        Scrape Common Crawl index to get latest graph.

        Returns:
            Latest graph ID (e.g., "cc-main-2026-01") or None if unavailable
        """
        try:
            response = requests.get(CC_INDEX_URL, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find all links to graph directories
            # Format: cc-main-YYYY-mmm-mmm-mmm/
            graph_pattern = re.compile(r'cc-main-\d{4}-[a-z]{3}(-[a-z]{3})?(-[a-z]{3})?')

            graphs = []
            for link in soup.find_all('a'):
                href = link.get('href', '')
                match = graph_pattern.search(href)
                if match:
                    graphs.append(match.group(0))

            if not graphs:
                return None

            # Sort by year and month (latest first)
            graphs.sort(reverse=True)
            return graphs[0]

        except Exception:
            # Fallback to metadata if available
            if GRAPH_METADATA_FILE.exists():
                with open(GRAPH_METADATA_FILE, 'r') as f:
                    metadata = json.load(f)
                    return metadata.get('graph_id')
            return None

    def fetch_backlinks(
        self,
        domain: str,
        quality_filter: bool = True,
        min_links: int = None,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Dict:
        """
        Fetch backlinks for a domain from Common Crawl.

        Args:
            domain: Target domain (e.g., "example.com")
            quality_filter: Apply spam filters
            min_links: Minimum link count threshold
            progress_callback: Function to call with progress updates

        Returns:
            Dictionary with referring_domains, total_backlinks, quality_filtered, etc.
        """
        if min_links is None:
            min_links = self.spam_config.get('min_link_count', MIN_LINK_COUNT)

        # Ensure we have a current graph
        if not self.current_graph:
            if progress_callback:
                progress_callback("Checking for latest graph...")
            self.check_for_updates()

        if not self.current_graph:
            return {'error': 'Unable to determine latest Common Crawl graph'}

        # Step 1: Get/update vertex index
        if progress_callback:
            progress_callback("Building domain index...")
        self._ensure_vertex_index(progress_callback)

        # Step 2: Find target domain vertex ID
        target_id = self._get_vertex_id(domain)
        if not target_id:
            return {
                'error': f'Domain {domain} not found in graph',
                'suggestion': 'Try a larger/more popular domain, or the domain may be too new',
                'referring_domains': [],
                'total_backlinks': 0
            }

        # Step 3: Stream edges file and find backlinks
        if progress_callback:
            progress_callback(f"Streaming backlinks data from S3 (target vertex: {target_id})...")
        raw_backlinks = self._stream_backlinks(target_id, progress_callback)

        if len(raw_backlinks) == 0:
            return {
                'referring_domains': [],
                'total_backlinks': 0,
                'quality_filtered': 0,
                'message': f'No backlinks found for {domain} in current graph',
                'graph_date': self.current_graph
            }

        # Step 4: Aggregate by referring domain
        aggregated = self._aggregate_backlinks(raw_backlinks)

        # Step 5: Apply quality filters
        if quality_filter:
            if progress_callback:
                progress_callback("Applying quality filters...")
            filtered = self._filter_spam(aggregated, min_links)
        else:
            filtered = aggregated

        return {
            'referring_domains': filtered,
            'total_backlinks': len(aggregated),
            'quality_filtered': len(filtered),
            'graph_date': self.current_graph,
            'fetched_at': datetime.utcnow().isoformat()
        }

    def _ensure_vertex_index(self, progress_callback: Optional[Callable[[str], None]] = None):
        """
        Build domain -> vertex_id index by streaming vertices file.
        Cache locally for future queries.
        """
        cache_file = CACHE_DIR / f'vertices_{self.current_graph}.pkl'

        if cache_file.exists():
            # Load from cache
            if progress_callback:
                progress_callback("Loading cached vertex index...")
            with open(cache_file, 'rb') as f:
                self.vertex_index = pickle.load(f)
            return

        # Stream from S3 and build index
        if progress_callback:
            progress_callback("Downloading vertex index from S3 (this may take 45-90s)...")

        vertices_path = f"{CC_S3_BASE}{self.current_graph}/domain/vertices.txt.gz"

        try:
            # Stream vertices file
            result = subprocess.run(
                ['aws', 's3', 'cp', '--no-sign-request', vertices_path, '-'],
                capture_output=True,
                timeout=300,  # 5 minute timeout
                check=True
            )

            # Parse vertices
            self.vertex_index = {}
            with gzip.open(result.stdout, 'rt') as f:
                for line_num, line in enumerate(f, 1):
                    # Format: <id, reversed_domain, num_hosts>
                    # Example: "123 com.example 5"
                    parts = line.strip().split('\t')
                    if len(parts) >= 2:
                        vertex_id = int(parts[0])
                        reversed_domain = parts[1]
                        self.vertex_index[reversed_domain] = vertex_id

                    # Progress update every 1M vertices
                    if progress_callback and line_num % 1000000 == 0:
                        progress_callback(f"Processed {line_num // 1000000}M vertices...")

            # Save to cache
            with open(cache_file, 'wb') as f:
                pickle.dump(self.vertex_index, f)

            if progress_callback:
                progress_callback(f"Vertex index built: {len(self.vertex_index):,} domains")

        except subprocess.TimeoutExpired:
            raise Exception("S3 query timeout (>5 min). Try again later or check connection.")
        except subprocess.CalledProcessError as e:
            raise Exception(f"S3 access failed: {e.stderr.decode() if e.stderr else 'Unknown error'}")
        except FileNotFoundError:
            raise Exception("AWS CLI not installed. Install: brew install awscli (macOS) or apt-get install awscli (Linux)")

    def _get_vertex_id(self, domain: str) -> Optional[int]:
        """
        Get vertex ID for a domain.

        Args:
            domain: Forward domain (e.g., "example.com")

        Returns:
            Vertex ID or None if not found
        """
        # Reverse domain format: com.example <- example.com
        reversed_domain = '.'.join(reversed(domain.split('.')))
        return self.vertex_index.get(reversed_domain)

    def _stream_backlinks(
        self,
        target_id: int,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> List[Tuple[int, int]]:
        """
        Stream edges-t.txt.gz to find all edges pointing TO target_id.

        Args:
            target_id: Target vertex ID
            progress_callback: Progress callback function

        Returns:
            List of (from_id, to_id) tuples
        """
        edges_path = f"{CC_S3_BASE}{self.current_graph}/domain/edges-t.txt.gz"

        try:
            # Stream edges file and grep for target
            # Format: <from_id, to_id>
            # The transposed file is sorted by to_id, so we can search efficiently

            if progress_callback:
                progress_callback("Streaming edge data (this may take 30-90s)...")

            # Use aws s3 cp piped through gzip and grep
            aws_process = subprocess.Popen(
                ['aws', 's3', 'cp', '--no-sign-request', edges_path, '-'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            gzip_process = subprocess.Popen(
                ['gzip', '-d'],
                stdin=aws_process.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            aws_process.stdout.close()

            # Read and parse edges
            edges = []
            with gzip_process.stdout as f:
                for line_num, line in enumerate(f, 1):
                    # Parse edge: from_id \t to_id
                    parts = line.decode('utf-8').strip().split('\t')
                    if len(parts) == 2:
                        from_id = int(parts[0])
                        to_id = int(parts[1])

                        if to_id == target_id:
                            edges.append((from_id, to_id))

                    # Progress update
                    if progress_callback and line_num % 10000000 == 0:
                        progress_callback(f"Scanned {line_num // 1000000}M edges, found {len(edges)} backlinks...")

            gzip_process.wait()
            aws_process.wait()

            return edges

        except Exception as e:
            raise Exception(f"Error streaming edges: {str(e)}")

    def _aggregate_backlinks(self, edges: List[Tuple[int, int]]) -> List[Dict]:
        """
        Aggregate edges by referring domain and count links.

        Args:
            edges: List of (from_id, to_id) tuples

        Returns:
            List of {domain, link_count, vertex_id}
        """
        link_counts = defaultdict(int)
        for from_id, to_id in edges:
            link_counts[from_id] += 1

        # Convert vertex IDs back to domains
        result = []
        reverse_index = {v: k for k, v in self.vertex_index.items()}

        for vertex_id, count in link_counts.items():
            reversed_domain = reverse_index.get(vertex_id, f'unknown_{vertex_id}')
            # Un-reverse domain: com.example -> example.com
            domain = '.'.join(reversed(reversed_domain.split('.')))

            result.append({
                'domain': domain,
                'link_count': count,
                'vertex_id': vertex_id
            })

        return result

    def _filter_spam(self, backlinks: List[Dict], min_links: int) -> List[Dict]:
        """
        Filter spam and low-quality backlinks.

        Criteria:
        1. Link count >= min_links
        2. Not in spam TLDs
        3. No spam keywords in domain
        4. Calculate quality score

        Args:
            backlinks: List of backlink dictionaries
            min_links: Minimum link count threshold

        Returns:
            Filtered and scored backlinks
        """
        filtered = []

        spam_tlds = self.spam_config.get('spam_tlds', SPAM_TLDS)
        spam_keywords = self.spam_config.get('spam_keywords', SPAM_KEYWORDS)

        for bl in backlinks:
            domain = bl['domain']
            link_count = bl['link_count']

            # Filter 1: Link count threshold
            if link_count < min_links:
                continue

            # Filter 2: Spam TLDs
            if any(domain.endswith(tld) for tld in spam_tlds):
                continue

            # Filter 3: Spam keywords
            domain_lower = domain.lower()
            if any(kw in domain_lower for kw in spam_keywords):
                continue

            # Calculate quality score (0-1)
            quality_score = self._calculate_quality(bl)
            bl['quality_score'] = quality_score

            filtered.append(bl)

        # Sort by quality score descending
        filtered.sort(key=lambda x: (x['quality_score'], x['link_count']), reverse=True)

        return filtered

    def _calculate_quality(self, backlink: Dict) -> float:
        """
        Calculate quality score for a backlink (0-1).

        Factors:
        - Link count (more is better)
        - Domain TLD (.edu, .gov = higher)
        - Domain length (shorter = better, likely branded)
        - No hyphens/numbers (cleaner = better)

        Args:
            backlink: Backlink dictionary

        Returns:
            Quality score between 0 and 1
        """
        score = 0.5  # Base score
        domain = backlink['domain']
        link_count = backlink['link_count']

        trusted_tlds = self.spam_config.get('trusted_tlds', ['.edu', '.gov', '.org'])

        # Factor 1: Link count (log scale)
        score += min(0.3, math.log10(link_count) / 10)

        # Factor 2: TLD bonus
        if domain.endswith('.edu') or domain.endswith('.gov'):
            score += 0.2
        elif domain.endswith('.org'):
            score += 0.1

        # Factor 3: Domain cleanliness
        domain_parts = domain.split('.')
        if len(domain_parts) >= 2:
            domain_name = domain_parts[-2]  # Get the main domain name

            if '-' not in domain_name:
                score += 0.05
            if not any(c.isdigit() for c in domain_name):
                score += 0.05
            if len(domain_name) < 15:
                score += 0.05

        return min(1.0, score)


def load_spam_config() -> dict:
    """Load spam filter configuration."""
    config_file = CACHE_DIR / 'spam_filters.json'

    if config_file.exists():
        with open(config_file, 'r') as f:
            return json.load(f)
    else:
        return DEFAULT_SPAM_CONFIG


def save_spam_config(config: dict):
    """Save spam filter configuration."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    config_file = CACHE_DIR / 'spam_filters.json'

    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
