"""
Google Search Console integration for traffic data.
"""

import os
import pickle
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from urllib.parse import urlparse

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Scopes required for GSC API
SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']

# Token storage
TOKEN_PATH = Path.home() / '.seo_audit' / 'gsc_token.pickle'
CREDENTIALS_PATH = Path.home() / '.seo_audit' / 'gsc_credentials.json'


class GSCClient:
    """Google Search Console API client."""

    def __init__(self):
        self.credentials = None
        self.service = None

    def authenticate(self, credentials_file: Optional[str] = None) -> bool:
        """
        Authenticate with Google Search Console.

        First time:
        1. Download OAuth credentials from Google Cloud Console
        2. Save as gsc_credentials.json
        3. Run: audit gsc-auth --credentials /path/to/gsc_credentials.json

        Subsequent times:
        - Token is stored and auto-refreshed
        """
        # Check for existing token
        if TOKEN_PATH.exists():
            with open(TOKEN_PATH, 'rb') as token:
                self.credentials = pickle.load(token)

        # Refresh token if expired
        if self.credentials and self.credentials.expired and self.credentials.refresh_token:
            try:
                self.credentials.refresh(Request())
            except Exception as e:
                print(f"Token refresh failed: {e}")
                self.credentials = None

        # New authentication flow
        if not self.credentials or not self.credentials.valid:
            creds_path = credentials_file or CREDENTIALS_PATH

            if not Path(creds_path).exists():
                print(f"\n❌ Credentials file not found: {creds_path}")
                print("\n📋 Setup Instructions:")
                print("1. Go to https://console.cloud.google.com/")
                print("2. Create a project (or select existing)")
                print("3. Enable 'Google Search Console API'")
                print("4. Create OAuth 2.0 credentials (Desktop app)")
                print("5. Download credentials JSON")
                print(f"6. Save to: {CREDENTIALS_PATH}")
                print(f"7. Run: audit gsc-auth --credentials {CREDENTIALS_PATH}")
                return False

            try:
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                self.credentials = flow.run_local_server(port=0)

                # Save token for future use
                TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
                with open(TOKEN_PATH, 'wb') as token:
                    pickle.dump(self.credentials, token)

                print("✅ Authentication successful!")
                return True

            except Exception as e:
                print(f"❌ Authentication failed: {e}")
                return False

        # Build service
        try:
            self.service = build('searchconsole', 'v1', credentials=self.credentials)
            return True
        except Exception as e:
            print(f"❌ Failed to build GSC service: {e}")
            return False

    def get_sites(self) -> List[str]:
        """Get list of sites user has access to."""
        if not self.service:
            if not self.authenticate():
                return []

        try:
            response = self.service.sites().list().execute()
            sites = [site['siteUrl'] for site in response.get('siteEntry', [])]
            return sites
        except Exception as e:
            print(f"Error fetching sites: {e}")
            return []

    def fetch_data(self, site_url: str, days: int = 90) -> Dict:
        """
        Fetch Search Console data for the last N days.

        Returns:
        {
            'pages': {
                'https://example.com/page': {
                    'clicks': 123,
                    'impressions': 4567,
                    'ctr': 0.027,
                    'position': 5.4,
                    'queries': [
                        {'query': 'keyword', 'clicks': 10, 'impressions': 100, 'position': 3.2},
                        ...
                    ]
                }
            },
            'total_clicks': 1234,
            'total_impressions': 45678,
            'date_range': {'start': '2026-01-01', 'end': '2026-03-31'}
        }
        """
        if not self.service:
            if not self.authenticate():
                return {}

        # Date range
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)

        # Auto-match to available GSC property
        original_url = site_url
        matched_property = self.find_matching_property(site_url)

        if matched_property:
            site_url = matched_property
            if matched_property != self._normalize_site_url(original_url):
                print(f"📍 Matched to GSC property: {matched_property}")
        else:
            # Fall back to normalized URL
            site_url = self._normalize_site_url(site_url)
            available_sites = self.get_sites()
            if available_sites:
                print(f"⚠️  No matching GSC property found for {site_url}")
                print(f"   Available properties: {', '.join(available_sites)}")
                print(f"   Make sure this site is verified in your Google Search Console.")
                return {}

        print(f"Fetching GSC data for {site_url} ({start_date} to {end_date})...")

        try:
            # Request 1: Page-level data
            page_request = {
                'startDate': start_date.strftime('%Y-%m-%d'),
                'endDate': end_date.strftime('%Y-%m-%d'),
                'dimensions': ['page'],
                'rowLimit': 25000  # Max allowed
            }

            page_response = self.service.searchanalytics().query(
                siteUrl=site_url,
                body=page_request
            ).execute()

            # Process page data
            pages_data = {}
            total_clicks = 0
            total_impressions = 0

            for row in page_response.get('rows', []):
                page = row['keys'][0]
                clicks = row['clicks']
                impressions = row['impressions']
                ctr = row['ctr']
                position = row['position']

                pages_data[page] = {
                    'clicks': clicks,
                    'impressions': impressions,
                    'ctr': ctr,
                    'position': position,
                    'queries': []
                }

                total_clicks += clicks
                total_impressions += impressions

            print(f"  Found {len(pages_data)} pages with traffic")

            # Request 2: Query data per page (for top pages only)
            top_pages = sorted(pages_data.keys(), key=lambda p: pages_data[p]['clicks'], reverse=True)[:100]

            for i, page in enumerate(top_pages):
                if (i + 1) % 10 == 0:
                    print(f"  Fetching queries for page {i+1}/{len(top_pages)}...")

                query_request = {
                    'startDate': start_date.strftime('%Y-%m-%d'),
                    'endDate': end_date.strftime('%Y-%m-%d'),
                    'dimensions': ['query'],
                    'dimensionFilterGroups': [{
                        'filters': [{
                            'dimension': 'page',
                            'operator': 'equals',
                            'expression': page
                        }]
                    }],
                    'rowLimit': 25
                }

                try:
                    query_response = self.service.searchanalytics().query(
                        siteUrl=site_url,
                        body=query_request
                    ).execute()

                    queries = []
                    for row in query_response.get('rows', []):
                        queries.append({
                            'query': row['keys'][0],
                            'clicks': row['clicks'],
                            'impressions': row['impressions'],
                            'ctr': row['ctr'],
                            'position': row['position']
                        })

                    pages_data[page]['queries'] = queries

                except Exception as e:
                    print(f"  Warning: Could not fetch queries for {page}: {e}")
                    continue

            return {
                'pages': pages_data,
                'total_clicks': total_clicks,
                'total_impressions': total_impressions,
                'date_range': {
                    'start': start_date.strftime('%Y-%m-%d'),
                    'end': end_date.strftime('%Y-%m-%d')
                }
            }

        except Exception as e:
            print(f"❌ Error fetching GSC data: {e}")
            return {}

    def _normalize_site_url(self, url: str) -> str:
        """
        Normalize URL to GSC site property format.

        Examples:
        - https://example.com -> https://example.com/
        - http://example.com -> http://example.com/
        - sc-domain:example.com -> sc-domain:example.com
        """
        if url.startswith('sc-domain:'):
            return url

        parsed = urlparse(url)
        normalized = f"{parsed.scheme}://{parsed.netloc}/"
        return normalized

    def _extract_domain(self, url: str) -> str:
        """Extract the base domain from a URL (without www prefix)."""
        if url.startswith('sc-domain:'):
            return url.replace('sc-domain:', '')

        parsed = urlparse(url)
        domain = parsed.netloc

        # Remove www. prefix if present
        if domain.startswith('www.'):
            domain = domain[4:]

        return domain

    def find_matching_property(self, target_url: str) -> Optional[str]:
        """
        Find a GSC property that matches the target URL.

        Checks against all available properties and matches by domain,
        handling various property formats (URL prefix, domain property, www/non-www).

        Returns the matching GSC property URL, or None if no match found.
        """
        sites = self.get_sites()
        if not sites:
            return None

        target_domain = self._extract_domain(target_url)

        # Priority order for matching:
        # 1. Exact match (normalized)
        # 2. Domain property (sc-domain:)
        # 3. Same domain with different prefix (www/non-www)
        # 4. Same domain with different protocol (http/https)

        normalized_target = self._normalize_site_url(target_url)

        # Check for exact match first
        if normalized_target in sites:
            return normalized_target

        # Check for domain property
        domain_property = f"sc-domain:{target_domain}"
        if domain_property in sites:
            return domain_property

        # Check for www variant
        parsed = urlparse(target_url)
        if parsed.netloc.startswith('www.'):
            # Target has www, check for non-www version
            non_www = f"{parsed.scheme}://{parsed.netloc[4:]}/"
            if non_www in sites:
                return non_www
        else:
            # Target doesn't have www, check for www version
            with_www = f"{parsed.scheme}://www.{parsed.netloc}/"
            if with_www in sites:
                return with_www

        # Check for protocol variants (http vs https)
        for site in sites:
            site_domain = self._extract_domain(site)
            if site_domain == target_domain:
                return site

        return None

    def test_connection(self) -> bool:
        """Test if authentication and API access work."""
        if not self.authenticate():
            return False

        sites = self.get_sites()
        if sites:
            print(f"\n✅ Connected! You have access to {len(sites)} site(s):")
            for site in sites:
                print(f"  - {site}")
            return True
        else:
            print("\n❌ No sites found. Make sure you've added your site to Search Console.")
            return False
