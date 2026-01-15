"""
Audit checks module - pluggable SEO checks.
"""

from .base import BaseCheck
from .broken_links import BrokenLinksCheck
from .titles import TitlesCheck
from .meta_description import MetaDescriptionCheck
from .headings import HeadingsCheck
from .redirects import RedirectsCheck

# Registry of all available checks
ALL_CHECKS = [
    BrokenLinksCheck,
    TitlesCheck,
    MetaDescriptionCheck,
    HeadingsCheck,
    RedirectsCheck,
]

__all__ = [
    'BaseCheck',
    'BrokenLinksCheck',
    'TitlesCheck',
    'MetaDescriptionCheck',
    'HeadingsCheck',
    'RedirectsCheck',
    'ALL_CHECKS',
]
