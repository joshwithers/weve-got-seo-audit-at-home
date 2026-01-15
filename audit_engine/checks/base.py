"""
Base class for all audit checks.
"""

from abc import ABC, abstractmethod
from typing import List

from ..database import Database
from ..models import Issue


class BaseCheck(ABC):
    """
    Base class for audit checks.
    Each check analyzes the crawled data and generates issues.
    """

    def __init__(self, database: Database):
        self.db = database

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the check."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what this check does."""
        pass

    @abstractmethod
    def run(self) -> List[Issue]:
        """
        Execute the check and return a list of issues found.
        Should not modify the database directly - return issues instead.
        """
        pass

    def execute(self) -> List[Issue]:
        """
        Execute the check and save issues to database.
        Returns the list of issues found.
        """
        print(f"Running check: {self.name}")
        issues = self.run()

        # Save issues to database
        for issue in issues:
            self.db.save_issue(issue)

        if issues:
            print(f"  Found {len(issues)} issue(s)")
        else:
            print(f"  No issues found")

        return issues
