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
from .cc_integration import CCClient, load_spam_config, save_spam_config


@click.group()
@click.version_option(version="0.3.0")
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
@click.option('--with-gsc', is_flag=True, help='Include Google Search Console traffic data')
@click.option('--gsc-days', default=90, help='Days of GSC data to fetch (default: 90)')
@click.option('--with-backlinks', is_flag=True, help='Include Common Crawl backlinks data')
@click.option('--min-backlinks', default=2, help='Minimum links per domain for backlinks (default: 2)')
def run(url, depth, max_pages, format, output, db, delay, no_robots, business_name, prepared_by, export_dir, with_gsc, gsc_days, with_backlinks, min_backlinks):
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

    # Fetch GSC data if requested
    if with_gsc:
        click.echo("\n=== FETCHING GOOGLE SEARCH CONSOLE DATA ===")
        gsc = GSCClient()
        if not gsc.authenticate():
            click.echo("\n⚠️  Not authenticated with Google Search Console")
            click.echo("\nTo use --with-gsc, you need to authenticate first:")
            click.echo("1. Get OAuth credentials from Google Cloud Console")
            click.echo("2. Run: audit gsc-auth --credentials /path/to/credentials.json")
            click.echo("\nSee GSC_SETUP_GUIDE.md for detailed instructions.")

            if click.confirm("\nDo you want to authenticate now?", default=False):
                creds_path = click.prompt("Enter path to credentials JSON file", type=str)
                if gsc.authenticate(creds_path):
                    click.echo("✅ Authentication successful! Continuing with GSC data...")
                else:
                    click.echo("❌ Authentication failed. Continuing without GSC data...")
                    gsc = None
            else:
                click.echo("⏭️  Skipping GSC data. Continuing with audit...")
                gsc = None

        if gsc:
            gsc_data = gsc.fetch_data(url, days=gsc_days)

            if gsc_data and gsc_data.get('pages'):
                click.echo(f"\n💾 Saving GSC data...")
                date_range = gsc_data['date_range']
                saved_count = 0

                for page_url, page_data in gsc_data['pages'].items():
                    database.save_gsc_page_data(page_url, page_data, date_range)

                    if page_data.get('queries'):
                        database.save_gsc_queries(page_url, page_data['queries'], date_range)

                    saved_count += 1
                    if saved_count % 50 == 0:
                        click.echo(f"  Saved {saved_count}/{len(gsc_data['pages'])} pages...")

                click.echo(f"\n✅ Saved GSC data for {len(gsc_data['pages'])} pages")
                click.echo(f"   Total clicks: {gsc_data['total_clicks']:,}")
                click.echo(f"   Total impressions: {gsc_data['total_impressions']:,}")
            else:
                click.echo("⚠️  No GSC data found. Continuing without traffic data...")

    # Fetch Common Crawl backlinks if requested
    if with_backlinks:
        click.echo("\n=== FETCHING COMMON CRAWL BACKLINKS ===")
        from urllib.parse import urlparse

        # Extract domain from URL
        domain = urlparse(url).netloc

        cc = CCClient()

        # Test connection first
        click.echo("Testing Common Crawl S3 access...")
        if not cc.test_connection():
            click.echo("\n❌ Cannot access Common Crawl S3")
            click.echo("\nPrerequisites:")
            click.echo("  - AWS CLI must be installed")
            click.echo("    macOS: brew install awscli")
            click.echo("    Linux: apt-get install awscli")
            click.echo("\nTo test: audit cc-auth")
            click.echo("\n⏭️  Skipping backlinks data. Continuing with audit...")
        else:
            # Auto-check for updates
            new_graph = cc.check_for_updates()
            if new_graph:
                click.echo(f"📊 Using graph: {new_graph}")

            # Progress callback
            def progress(msg):
                click.echo(f"  {msg}")

            try:
                backlinks_data = cc.fetch_backlinks(
                    domain,
                    quality_filter=True,
                    min_links=min_backlinks,
                    progress_callback=progress
                )

                if 'error' not in backlinks_data:
                    click.echo(f"\n💾 Saving backlinks to database...")
                    database.save_cc_backlinks(
                        domain,
                        backlinks_data['referring_domains'],
                        backlinks_data['graph_date']
                    )

                    click.echo(f"\n✅ Found {backlinks_data['quality_filtered']} quality backlinks")
                    click.echo(f"   Total referring domains: {backlinks_data['total_backlinks']}")
                    click.echo(f"   Graph date: {backlinks_data['graph_date']}")
                else:
                    click.echo(f"\n⚠️  {backlinks_data['error']}")
                    if 'suggestion' in backlinks_data:
                        click.echo(f"   {backlinks_data['suggestion']}")
            except Exception as e:
                click.echo(f"\n⚠️  Backlinks fetch failed: {e}")
                click.echo("Continuing with audit...")

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


@cli.command('gsc-auth')
@click.option('--credentials', help='Path to Google Cloud OAuth credentials JSON file')
def gsc_auth(credentials):
    """
    Authenticate with Google Search Console.

    Setup instructions:
    1. Go to https://console.cloud.google.com/
    2. Create a new project (or select existing)
    3. Enable "Google Search Console API"
    4. Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client ID"
    5. Application type: "Desktop app"
    6. Download the credentials JSON file
    7. Run: audit gsc-auth --credentials /path/to/credentials.json

    The auth token will be saved for future use.

    Example:
        audit gsc-auth --credentials ~/Downloads/client_secret.json
    """
    click.echo("🔐 Google Search Console Authentication\n")

    gsc = GSCClient()

    if gsc.authenticate(credentials):
        click.echo("\n✅ Authentication successful!")
        click.echo("\nYou can now run: audit gsc-test")
    else:
        click.echo("\n❌ Authentication failed")
        sys.exit(1)


@cli.command('gsc-test')
def gsc_test():
    """
    Test Google Search Console connection.

    Verifies that authentication works and lists available sites.

    Example:
        audit gsc-test
    """
    click.echo("🔍 Testing Google Search Console connection...\n")

    gsc = GSCClient()

    if gsc.test_connection():
        click.echo("\n✅ GSC connection working!")
    else:
        click.echo("\n❌ Connection test failed")
        click.echo("\nRun 'audit gsc-auth' to authenticate first")
        sys.exit(1)


@cli.command('gsc-fetch')
@click.argument('url')
@click.option('--days', default=90, help='Number of days of data to fetch (default: 90)')
@click.option('--db', default='audit.db', help='SQLite database file (default: audit.db)')
def gsc_fetch(url, days, db):
    """
    Fetch Google Search Console data for a site.

    This will fetch traffic data (clicks, impressions, queries) and store
    it in the database for use in reports.

    Example:
        audit gsc-fetch https://example.com
        audit gsc-fetch https://example.com --days 180
    """
    click.echo(f"📊 Fetching GSC data for: {url}")
    click.echo(f"Date range: Last {days} days\n")

    # Initialize GSC client
    gsc = GSCClient()
    if not gsc.authenticate():
        click.echo("❌ Authentication failed. Run 'audit gsc-auth' first.")
        sys.exit(1)

    # Fetch data
    data = gsc.fetch_data(url, days=days)

    if not data or not data.get('pages'):
        click.echo("❌ No data found. Make sure the site is added to Search Console.")
        sys.exit(1)

    # Save to database
    database = Database(db)
    date_range = data['date_range']

    click.echo(f"\n💾 Saving data to database...")
    saved_count = 0

    for page_url, page_data in data['pages'].items():
        database.save_gsc_page_data(page_url, page_data, date_range)

        if page_data.get('queries'):
            database.save_gsc_queries(page_url, page_data['queries'], date_range)

        saved_count += 1
        if saved_count % 50 == 0:
            click.echo(f"  Saved {saved_count}/{len(data['pages'])} pages...")

    click.echo(f"\n✅ Saved GSC data for {len(data['pages'])} pages")
    click.echo(f"   Total clicks: {data['total_clicks']:,}")
    click.echo(f"   Total impressions: {data['total_impressions']:,}")
    click.echo(f"   Date range: {date_range['start']} to {date_range['end']}")


@cli.command('cc-auth')
def cc_auth():
    """
    Test Common Crawl S3 access.

    Verifies that AWS CLI is installed and can access Common Crawl data.
    No authentication required (public data).

    Prerequisites:
    - AWS CLI must be installed (brew install awscli on macOS)

    Example:
        audit cc-auth
    """
    click.echo("🔍 Testing Common Crawl access...\n")

    # Check AWS CLI installed
    import subprocess
    try:
        result = subprocess.run(['aws', '--version'], capture_output=True, text=True)
        click.echo(f"✅ AWS CLI found: {result.stdout.strip()}")
    except FileNotFoundError:
        click.echo("❌ AWS CLI not found")
        click.echo("\nInstall AWS CLI:")
        click.echo("  macOS:   brew install awscli")
        click.echo("  Linux:   apt-get install awscli")
        click.echo("  Windows: Download from aws.amazon.com/cli")
        sys.exit(1)

    # Test S3 access
    cc = CCClient()
    if cc.test_connection():
        click.echo("✅ Common Crawl S3 access working!")

        # Show latest graph info
        latest_graph = cc._get_latest_graph_id()
        if latest_graph:
            click.echo(f"\n📊 Latest graph: {latest_graph}")
    else:
        click.echo("❌ Cannot access Common Crawl S3")
        sys.exit(1)


@cli.command('cc-fetch')
@click.argument('domain')
@click.option('--db', default='audit.db', help='SQLite database file (default: audit.db)')
@click.option('--min-links', default=2, help='Minimum links from same domain (default: 2)')
@click.option('--no-filter', is_flag=True, help='Skip spam filtering')
def cc_fetch(domain, db, min_links, no_filter):
    """
    Fetch Common Crawl backlinks for a domain.

    This will query the Common Crawl hyperlinkgraph and store
    quality-filtered backlinks in the database.

    Example:
        audit cc-fetch example.com
        audit cc-fetch example.com --min-links 5
        audit cc-fetch marriedbyjosh.com
    """
    from urllib.parse import urlparse

    click.echo(f"🔗 Fetching backlinks for: {domain}\n")

    # Extract domain from URL if needed
    if domain.startswith('http'):
        domain = urlparse(domain).netloc

    # Initialize client
    cc = CCClient()

    # Check for updates
    click.echo("Checking for graph updates...")
    new_graph = cc.check_for_updates()
    if new_graph:
        click.echo(f"📊 Using graph: {new_graph}")

    # Progress indicator
    def progress(msg):
        click.echo(f"  {msg}")

    # Fetch backlinks
    try:
        data = cc.fetch_backlinks(
            domain,
            quality_filter=not no_filter,
            min_links=min_links,
            progress_callback=progress
        )
    except Exception as e:
        click.echo(f"❌ Error fetching backlinks: {e}")
        sys.exit(1)

    if 'error' in data:
        click.echo(f"❌ {data['error']}")
        if 'suggestion' in data:
            click.echo(f"   {data['suggestion']}")
        sys.exit(1)

    # Save to database
    database = Database(db)
    click.echo(f"\n💾 Saving backlinks to database...")
    database.save_cc_backlinks(domain, data['referring_domains'], data['graph_date'])

    # Summary
    click.echo(f"\n✅ Found {data['total_backlinks']} referring domains")
    click.echo(f"   Quality filtered: {data['quality_filtered']} domains")
    click.echo(f"   Graph date: {data['graph_date']}")

    # Show top 10
    if data['referring_domains']:
        click.echo("\n🏆 Top 10 backlinks:")
        for i, bl in enumerate(data['referring_domains'][:10], 1):
            click.echo(f"  {i}. {bl['domain']} ({bl['link_count']} links, quality: {bl['quality_score']:.2f})")


@cli.command('cc-check-update')
def cc_check_update():
    """
    Check for new Common Crawl graph releases.

    Common Crawl releases new hyperlinkgraphs quarterly.
    This command checks if a newer graph is available.

    Example:
        audit cc-check-update
    """
    from .cc_integration import GRAPH_METADATA_FILE
    import json

    click.echo("🔍 Checking for Common Crawl updates...\n")

    cc = CCClient()
    latest = cc._get_latest_graph_id()

    if not latest:
        click.echo("❌ Unable to fetch latest graph info")
        sys.exit(1)

    # Check cached metadata
    if GRAPH_METADATA_FILE.exists():
        with open(GRAPH_METADATA_FILE, 'r') as f:
            cached = json.load(f)
            cached_graph = cached.get('graph_id')

        if cached_graph == latest:
            click.echo(f"✅ Using latest graph: {latest}")
        else:
            click.echo(f"📊 New graph available!")
            click.echo(f"   Current: {cached_graph}")
            click.echo(f"   Latest: {latest}")
            click.echo("\nRun 'audit cc-fetch' to use the new graph")
    else:
        click.echo(f"📊 Latest graph: {latest}")
        click.echo("\nRun 'audit cc-fetch <domain>' to start using Common Crawl backlinks")


@cli.command('cc-config')
@click.option('--show', is_flag=True, help='Show current configuration')
@click.option('--reset', is_flag=True, help='Reset to defaults')
def cc_config(show, reset):
    """
    Manage Common Crawl spam filter configuration.

    Configure spam filtering rules for backlink quality filtering.
    Settings are stored in ~/.seo_audit/cc_cache/spam_filters.json

    Example:
        audit cc-config --show
        audit cc-config --reset
    """
    from .cc_integration import CACHE_DIR, DEFAULT_SPAM_CONFIG

    config_file = CACHE_DIR / 'spam_filters.json'

    if reset:
        # Reset to defaults
        save_spam_config(DEFAULT_SPAM_CONFIG)
        click.echo(f"✅ Reset configuration to defaults")
        click.echo(f"   Config file: {config_file}")

    if show or reset:
        config = load_spam_config()
        click.echo("\n📋 Current Configuration:\n")
        click.echo(f"Min Link Count: {config.get('min_link_count', 2)}")
        click.echo(f"Min Quality Score: {config.get('min_quality_score', 0.3)}")
        click.echo(f"\nSpam TLDs ({len(config.get('spam_tlds', []))}):")
        spam_tlds = config.get('spam_tlds', [])
        click.echo("  " + ", ".join(spam_tlds[:10]) + ("..." if len(spam_tlds) > 10 else ""))
        click.echo(f"\nSpam Keywords ({len(config.get('spam_keywords', []))}):")
        spam_keywords = config.get('spam_keywords', [])
        click.echo("  " + ", ".join(spam_keywords[:10]) + ("..." if len(spam_keywords) > 10 else ""))
        click.echo(f"\n📝 Edit config: {config_file}")


if __name__ == '__main__':
    cli()
