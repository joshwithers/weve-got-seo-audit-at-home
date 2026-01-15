"""
Data models for the audit engine.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum


class Severity(str, Enum):
    """Issue severity levels."""
    ERROR = "error"
    WARNING = "warning"
    NOTICE = "notice"


class LinkType(str, Enum):
    """Type of link."""
    INTERNAL = "internal"
    EXTERNAL = "external"


@dataclass
class Page:
    """Represents a crawled web page."""
    url: str
    status_code: Optional[int] = None
    title: Optional[str] = None
    meta_description: Optional[str] = None
    canonical: Optional[str] = None
    robots_meta: Optional[str] = None
    h1_count: int = 0
    h1_text: Optional[str] = None
    redirect_to: Optional[str] = None
    depth: int = 0
    crawled_at: Optional[datetime] = None
    content_hash: Optional[str] = None


@dataclass
class Link:
    """Represents a link from one page to another."""
    source_url: str
    target_url: str
    link_text: Optional[str] = None
    link_type: LinkType = LinkType.INTERNAL
    is_broken: bool = False


@dataclass
class Issue:
    """Represents an audit issue."""
    issue_type: str
    severity: Severity
    description: str
    affected_url: Optional[str] = None
    details: Optional[dict] = None
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class CrawlMeta:
    """Metadata about a crawl session."""
    seed_url: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_pages: int = 0
    total_issues: int = 0
    config: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.started_at is None:
            self.started_at = datetime.utcnow()


@dataclass
class CrawlConfig:
    """Configuration for crawler behavior."""
    max_depth: int = 3
    max_pages: int = 1000
    respect_robots_txt: bool = True
    follow_redirects: bool = True
    timeout: int = 10
    user_agent: str = "SEO-Audit-Bot/1.0"
    delay_between_requests: float = 0.5
    exclude_extensions: list = field(default_factory=lambda: ['.pdf', '.epub', '.xml', '.txt', '.zip', '.gz', '.tar'])
    business_name: str = "SEO Audit Engine"
    prepared_by: str = ""
