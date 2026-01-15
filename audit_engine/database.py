"""
SQLite database layer for storing crawl data.
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, List
from contextlib import contextmanager
from pathlib import Path

from .models import Page, Link, Issue, CrawlMeta, Severity, LinkType


def _parse_datetime(dt_string: Optional[str]) -> Optional[datetime]:
    """Parse datetime string from SQLite."""
    if not dt_string:
        return None
    try:
        return datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return None


class Database:
    """Handles all database operations."""

    def __init__(self, db_path: str = "audit.db"):
        self.db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self):
        """Create tables if they don't exist."""
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    status_code INTEGER,
                    title TEXT,
                    meta_description TEXT,
                    canonical TEXT,
                    robots_meta TEXT,
                    h1_count INTEGER DEFAULT 0,
                    h1_text TEXT,
                    redirect_to TEXT,
                    depth INTEGER DEFAULT 0,
                    crawled_at TIMESTAMP,
                    content_hash TEXT
                );

                CREATE TABLE IF NOT EXISTS links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_url TEXT NOT NULL,
                    target_url TEXT NOT NULL,
                    link_text TEXT,
                    link_type TEXT NOT NULL,
                    is_broken BOOLEAN DEFAULT 0,
                    FOREIGN KEY (source_url) REFERENCES pages(url)
                );

                CREATE TABLE IF NOT EXISTS issues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    issue_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    description TEXT NOT NULL,
                    affected_url TEXT,
                    details TEXT,
                    created_at TIMESTAMP,
                    FOREIGN KEY (affected_url) REFERENCES pages(url)
                );

                CREATE TABLE IF NOT EXISTS crawl_meta (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    seed_url TEXT NOT NULL,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    total_pages INTEGER DEFAULT 0,
                    total_issues INTEGER DEFAULT 0,
                    config TEXT
                );

                CREATE TABLE IF NOT EXISTS gsc_page_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    clicks INTEGER DEFAULT 0,
                    impressions INTEGER DEFAULT 0,
                    ctr REAL DEFAULT 0,
                    position REAL DEFAULT 0,
                    date_start TEXT,
                    date_end TEXT,
                    fetched_at TIMESTAMP,
                    UNIQUE(url, date_start, date_end)
                );

                CREATE TABLE IF NOT EXISTS gsc_queries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    query TEXT NOT NULL,
                    clicks INTEGER DEFAULT 0,
                    impressions INTEGER DEFAULT 0,
                    ctr REAL DEFAULT 0,
                    position REAL DEFAULT 0,
                    date_start TEXT,
                    date_end TEXT,
                    FOREIGN KEY (url) REFERENCES pages(url)
                );

                CREATE INDEX IF NOT EXISTS idx_pages_url ON pages(url);
                CREATE INDEX IF NOT EXISTS idx_links_source ON links(source_url);
                CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_url);
                CREATE INDEX IF NOT EXISTS idx_issues_url ON issues(affected_url);
                CREATE INDEX IF NOT EXISTS idx_gsc_page_url ON gsc_page_data(url);
                CREATE INDEX IF NOT EXISTS idx_gsc_queries_url ON gsc_queries(url);
            """)

    @contextmanager
    def _connect(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def save_page(self, page: Page) -> None:
        """Save or update a page."""
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO pages (
                    url, status_code, title, meta_description, canonical,
                    robots_meta, h1_count, h1_text, redirect_to, depth,
                    crawled_at, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                page.url,
                page.status_code,
                page.title,
                page.meta_description,
                page.canonical,
                page.robots_meta,
                page.h1_count,
                page.h1_text,
                page.redirect_to,
                page.depth,
                page.crawled_at or datetime.utcnow(),
                page.content_hash
            ))

    def save_link(self, link: Link) -> None:
        """Save a link."""
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO links (
                    source_url, target_url, link_text, link_type, is_broken
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                link.source_url,
                link.target_url,
                link.link_text,
                link.link_type.value,
                link.is_broken
            ))

    def save_issue(self, issue: Issue) -> None:
        """Save an issue."""
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO issues (
                    issue_type, severity, description, affected_url, details, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                issue.issue_type,
                issue.severity.value,
                issue.description,
                issue.affected_url,
                json.dumps(issue.details) if issue.details else None,
                issue.created_at or datetime.utcnow()
            ))

    def save_crawl_meta(self, meta: CrawlMeta) -> int:
        """Save crawl metadata and return the ID."""
        with self._connect() as conn:
            cursor = conn.execute("""
                INSERT INTO crawl_meta (
                    seed_url, started_at, completed_at, total_pages, total_issues, config
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                meta.seed_url,
                meta.started_at,
                meta.completed_at,
                meta.total_pages,
                meta.total_issues,
                json.dumps(meta.config) if meta.config else None
            ))
            return cursor.lastrowid

    def update_crawl_meta(self, crawl_id: int, completed_at: datetime, total_pages: int, total_issues: int) -> None:
        """Update crawl metadata when crawl completes."""
        with self._connect() as conn:
            conn.execute("""
                UPDATE crawl_meta
                SET completed_at = ?, total_pages = ?, total_issues = ?
                WHERE id = ?
            """, (completed_at, total_pages, total_issues, crawl_id))

    def get_page(self, url: str) -> Optional[Page]:
        """Retrieve a page by URL."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM pages WHERE url = ?", (url,)).fetchone()
            if row:
                return Page(
                    url=row['url'],
                    status_code=row['status_code'],
                    title=row['title'],
                    meta_description=row['meta_description'],
                    canonical=row['canonical'],
                    robots_meta=row['robots_meta'],
                    h1_count=row['h1_count'],
                    h1_text=row['h1_text'],
                    redirect_to=row['redirect_to'],
                    depth=row['depth'],
                    crawled_at=_parse_datetime(row['crawled_at']),
                    content_hash=row['content_hash']
                )
            return None

    def get_all_pages(self) -> List[Page]:
        """Retrieve all pages."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM pages ORDER BY url").fetchall()
            return [
                Page(
                    url=row['url'],
                    status_code=row['status_code'],
                    title=row['title'],
                    meta_description=row['meta_description'],
                    canonical=row['canonical'],
                    robots_meta=row['robots_meta'],
                    h1_count=row['h1_count'],
                    h1_text=row['h1_text'],
                    redirect_to=row['redirect_to'],
                    depth=row['depth'],
                    crawled_at=_parse_datetime(row['crawled_at']),
                    content_hash=row['content_hash']
                )
                for row in rows
            ]

    def get_all_links(self) -> List[Link]:
        """Retrieve all links."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM links").fetchall()
            return [
                Link(
                    source_url=row['source_url'],
                    target_url=row['target_url'],
                    link_text=row['link_text'],
                    link_type=LinkType(row['link_type']),
                    is_broken=bool(row['is_broken'])
                )
                for row in rows
            ]

    def get_all_issues(self) -> List[Issue]:
        """Retrieve all issues."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM issues ORDER BY severity, issue_type").fetchall()
            return [
                Issue(
                    issue_type=row['issue_type'],
                    severity=Severity(row['severity']),
                    description=row['description'],
                    affected_url=row['affected_url'],
                    details=json.loads(row['details']) if row['details'] else None,
                    created_at=_parse_datetime(row['created_at'])
                )
                for row in rows
            ]

    def save_gsc_page_data(self, url: str, data: dict, date_range: dict) -> None:
        """Save Google Search Console page data."""
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO gsc_page_data (
                    url, clicks, impressions, ctr, position,
                    date_start, date_end, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                url,
                data.get('clicks', 0),
                data.get('impressions', 0),
                data.get('ctr', 0),
                data.get('position', 0),
                date_range['start'],
                date_range['end'],
                datetime.utcnow()
            ))

    def save_gsc_queries(self, url: str, queries: list, date_range: dict) -> None:
        """Save Google Search Console query data for a page."""
        with self._connect() as conn:
            # Clear existing queries for this URL and date range
            conn.execute("""
                DELETE FROM gsc_queries
                WHERE url = ? AND date_start = ? AND date_end = ?
            """, (url, date_range['start'], date_range['end']))

            # Insert new queries
            for query in queries:
                conn.execute("""
                    INSERT INTO gsc_queries (
                        url, query, clicks, impressions, ctr, position,
                        date_start, date_end
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    url,
                    query['query'],
                    query['clicks'],
                    query['impressions'],
                    query['ctr'],
                    query['position'],
                    date_range['start'],
                    date_range['end']
                ))

    def get_gsc_page_data(self, url: Optional[str] = None) -> dict:
        """Get GSC data for a specific page or all pages."""
        with self._connect() as conn:
            if url:
                row = conn.execute("""
                    SELECT * FROM gsc_page_data
                    WHERE url = ?
                    ORDER BY fetched_at DESC LIMIT 1
                """, (url,)).fetchone()

                if row:
                    return {
                        'url': row['url'],
                        'clicks': row['clicks'],
                        'impressions': row['impressions'],
                        'ctr': row['ctr'],
                        'position': row['position'],
                        'date_range': {
                            'start': row['date_start'],
                            'end': row['date_end']
                        }
                    }
                return {}
            else:
                rows = conn.execute("""
                    SELECT * FROM gsc_page_data
                    ORDER BY clicks DESC
                """).fetchall()

                return {
                    row['url']: {
                        'clicks': row['clicks'],
                        'impressions': row['impressions'],
                        'ctr': row['ctr'],
                        'position': row['position'],
                        'date_range': {
                            'start': row['date_start'],
                            'end': row['date_end']
                        }
                    }
                    for row in rows
                }

    def get_gsc_queries(self, url: str) -> list:
        """Get top queries for a specific page."""
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT * FROM gsc_queries
                WHERE url = ?
                ORDER BY clicks DESC
                LIMIT 25
            """, (url,)).fetchall()

            return [
                {
                    'query': row['query'],
                    'clicks': row['clicks'],
                    'impressions': row['impressions'],
                    'ctr': row['ctr'],
                    'position': row['position']
                }
                for row in rows
            ]

    def has_gsc_data(self) -> bool:
        """Check if GSC data exists in database."""
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) as count FROM gsc_page_data").fetchone()
            return row['count'] > 0

    def clear_all(self) -> None:
        """Clear all data from the database."""
        with self._connect() as conn:
            conn.executescript("""
                DELETE FROM gsc_queries;
                DELETE FROM gsc_page_data;
                DELETE FROM issues;
                DELETE FROM links;
                DELETE FROM pages;
                DELETE FROM crawl_meta;
            """)
