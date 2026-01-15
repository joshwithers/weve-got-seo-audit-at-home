"""
Command-line interface for the SEO audit tool.
"""

import sys
from datetime import datetime
from pathlib import Path

import click

from .crawler import Crawler
from .database import Database
from .exporter import Exporter
from .models import CrawlConfig, CrawlMeta
from .checks import ALL_CHECKS
from .gsc_integration import GSCClient


@click.group()
@click.version_option(version="0.2.0")
def cli():
    """
    Local-first SEO audit tool.

    Crawl websites and generate detailed SEO audit reports.
    """
    pass


@cli.command()
@click.argument('url')
@click.option('--depth', default=3, help='Maximum crawl depth (default: 3)')
@click.option('--max-pages', default=1000, help='Maximum pages to crawl (default: 1000)')
@click.option('--format', type=click.Choice(['json', 'markdown', 'html', 'csv', 'all']), default='markdown', help='Output format (default: markdown)')
@click.option('--output', '-o', help='Output file path (auto-generated if not specified)')
@click.option('--db', default='audit.db', help='SQLite database file (default: audit.db)')
@click.option('--delay', default=0.5, help='Delay between requests in seconds (default: 0.5)')
@click.option('--no-robots', is_flag=True, help='Ignore robots.txt')
@click.option('--business-name', default='SEO Audit Engine', help='Business name for report credits (default: SEO Audit Engine)')
@click.option('--prepared-by', default='', help='Name of person/team preparing the report')
@click.option('--export-dir', default='.', help='Directory for exports when using --format all (default: current directory)')
def run(url, depth, max_pages, format, output, db, delay, no_robots, business_name, prepared_by, export_dir):
    """
    Run a complete audit on a website.

    This will:
    1. Crawl the website starting from URL
    2. Extract SEO data from each page
    3. Run all audit checks
    4. Generate reports

    Example:
        audit run https://example.com
        audit run https://example.com --format html
        audit run https://example.com --format all --export-dir ./reports
        audit run https://example.com --depth 5 --max-pages 500
    """
    click.echo(f"Starting SEO audit of: {url}")
    click.echo(f"Max depth: {depth}, Max pages: {max_pages}")
    click.echo()

    # Initialize database
    database = Database(db)
    click.echo(f"Database: {db}")

    # Create crawl configuration
    config = CrawlConfig(
        max_depth=depth,
        max_pages=max_pages,
        respect_robots_txt=not no_robots,
        delay_between_requests=delay,
        business_name=business_name,
        prepared_by=prepared_by
    )

    # Record crawl metadata
    crawl_meta = CrawlMeta(
        seed_url=url,
        config=config.__dict__
    )
    crawl_id = database.save_crawl_meta(crawl_meta)

    # Run crawler
    click.echo("\n=== CRAWLING ===")
    crawler = Crawler(config, database)
    try:
        crawler.crawl(url)
    except KeyboardInterrupt:
        click.echo("\n\nCrawl interrupted by user")
        sys.exit(1)

    click.echo(f"\nCrawled {len(crawler.visited)} pages")

    # Run audit checks
    click.echo("\n=== RUNNING AUDIT CHECKS ===")
    all_issues = []
    for check_class in ALL_CHECKS:
        check = check_class(database)
        issues = check.execute()
        all_issues.extend(issues)

    # Update crawl metadata
    database.update_crawl_meta(
        crawl_id=crawl_id,
        completed_at=datetime.utcnow(),
        total_pages=len(crawler.visited),
        total_issues=len(all_issues)
    )

    # Export results
    click.echo("\n=== EXPORTING RESULTS ===")
    exporter = Exporter(database, business_name=business_name, prepared_by=prepared_by)

    if format == 'all':
        exporter.export_all(export_dir)
    elif format == 'json':
        output_file = output or 'audit_report.json'
        exporter.export_json(output_file)
    elif format == 'markdown':
        output_file = output or 'audit_report.md'
        exporter.export_markdown(output_file)
    elif format == 'html':
        output_file = output or 'audit_report.html'
        exporter.export_html(output_file)
    elif format == 'csv':
        exporter.export_issues_csv('audit_issues.csv')
        exporter.export_pages_csv('audit_pages.csv')

    # Print summary
    click.echo("\n=== AUDIT SUMMARY ===")
    click.echo(f"Total pages crawled: {len(crawler.visited)}")
    click.echo(f"Total issues found: {len(all_issues)}")

    # Count by severity
    errors = sum(1 for i in all_issues if i.severity.value == "error")
    warnings = sum(1 for i in all_issues if i.severity.value == "warning")
    notices = sum(1 for i in all_issues if i.severity.value == "notice")

    click.echo(f"  - Errors: {errors}")
    click.echo(f"  - Warnings: {warnings}")
    click.echo(f"  - Notices: {notices}")

    click.echo("\n✓ Audit complete!")


@cli.command()
@click.option('--db', default='audit.db', help='SQLite database file (default: audit.db)')
@click.option('--output', '-o', help='Output file path')
@click.option('--format', type=click.Choice(['json', 'markdown', 'html', 'csv', 'all']), default='markdown', help='Export format (default: markdown)')
@click.option('--business-name', default='SEO Audit Engine', help='Business name for report credits (default: SEO Audit Engine)')
@click.option('--prepared-by', default='', help='Name of person/team preparing the report')
def export(db, output, format, business_name, prepared_by):
    """
    Export audit data from the database.

    Use this to re-export data without re-crawling.

    Example:
        audit export --format markdown
        audit export --format html -o my_report.html
        audit export --format json -o report.json
        audit export --format csv
        audit export --format all
        audit export --format markdown --prepared-by "John Smith"
    """
    database = Database(db)
    exporter = Exporter(database, business_name=business_name, prepared_by=prepared_by)

    if format == 'json':
        output = output or 'audit_report.json'
        exporter.export_json(output)
    elif format == 'markdown':
        output = output or 'audit_report.md'
        exporter.export_markdown(output)
    elif format == 'html':
        output = output or 'audit_report.html'
        exporter.export_html(output)
    elif format == 'csv':
        exporter.export_issues_csv('audit_issues.csv')
        exporter.export_pages_csv('audit_pages.csv')
    elif format == 'all':
        exporter.export_all('.')

    click.echo("✓ Export complete!")


@cli.command()
@click.option('--db', default='audit.db', help='SQLite database file (default: audit.db)')
def clear(db):
    """
    Clear all data from the database.

    Use with caution - this deletes all crawl data.
    """
    if click.confirm(f"Are you sure you want to clear all data from {db}?"):
        database = Database(db)
        database.clear_all()
        click.echo("✓ Database cleared")
    else:
        click.echo("Cancelled")


@cli.command()
def checks():
    """
    List all available audit checks.
    """
    click.echo("Available audit checks:\n")
    for check_class in ALL_CHECKS:
        # Instantiate with None to get metadata (won't call run())
        check = check_class(None)
        click.echo(f"  • {check.name}")
        click.echo(f"    {check.description}")
        click.echo()


if __name__ == '__main__':
    cli()
