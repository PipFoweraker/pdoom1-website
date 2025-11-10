#!/usr/bin/env python3
"""
DreamHost Analytics Extraction Script

Extracts and processes web server logs from DreamHost VPS to generate
privacy-respecting analytics data.

Usage:
    python scripts/extract_analytics.py --help
    python scripts/extract_analytics.py --days 30
    python scripts/extract_analytics.py --month 2025-11
"""

import argparse
import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import urlparse
import hashlib

class AnalyticsExtractor:
    """Extract and process analytics from DreamHost web server logs."""

    def __init__(self, ssh_key: str, ssh_host: str = "ubuntu@208.113.200.215"):
        self.ssh_key = ssh_key
        self.ssh_host = ssh_host
        self.output_dir = Path("public/data/analytics/dreamhost")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Nginx log format: Combined Log Format
        # IP - - [timestamp] "METHOD /path HTTP/1.1" status size "referrer" "user-agent"
        self.log_pattern = re.compile(
            r'(?P<ip>[\d.]+) - - \[(?P<timestamp>[^\]]+)\] '
            r'"(?P<method>\w+) (?P<path>[^\s]+) HTTP/[^"]*" '
            r'(?P<status>\d+) (?P<size>\d+) '
            r'"(?P<referrer>[^"]*)" "(?P<user_agent>[^"]*)"'
        )

    def anonymize_ip(self, ip: str) -> str:
        """Anonymize IP address using SHA-256 hash (GDPR compliant)."""
        return hashlib.sha256(ip.encode()).hexdigest()[:16]

    def fetch_logs(self, days: int = 30) -> List[str]:
        """
        Fetch Nginx access logs from DreamHost VPS via SSH.

        Args:
            days: Number of days of logs to fetch

        Returns:
            List of log lines
        """
        print(f"Fetching logs from {self.ssh_host} (last {days} days)...")

        # DreamHost/Nginx logs are typically in /var/log/nginx/
        # We'll fetch the access log and recent rotated logs
        log_files = [
            "/var/log/nginx/access.log",
            "/var/log/nginx/access.log.1",
        ]

        # If we need more history, fetch compressed logs
        if days > 7:
            log_files.append("/var/log/nginx/access.log.2.gz")
        if days > 14:
            log_files.append("/var/log/nginx/access.log.3.gz")

        all_lines = []

        for log_file in log_files:
            try:
                # Check if file is compressed
                if log_file.endswith('.gz'):
                    cmd = f"zcat {log_file}"
                else:
                    cmd = f"cat {log_file}"

                result = subprocess.run(
                    ["ssh", "-i", self.ssh_key, self.ssh_host, cmd],
                    capture_output=True,
                    text=True,
                    timeout=60
                )

                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    all_lines.extend(lines)
                    print(f"  Fetched {len(lines)} lines from {log_file}")
                else:
                    print(f"  Warning: Could not fetch {log_file}")

            except subprocess.TimeoutExpired:
                print(f"  Warning: Timeout fetching {log_file}")
            except Exception as e:
                print(f"  Warning: Error fetching {log_file}: {e}")

        print(f"Total log lines fetched: {len(all_lines)}")
        return all_lines

    def parse_log_line(self, line: str) -> Dict:
        """Parse a single Nginx log line."""
        match = self.log_pattern.match(line)
        if not match:
            return None

        data = match.groupdict()

        # Parse timestamp
        try:
            # Format: 10/Nov/2025:14:30:00 +0000
            timestamp_str = data['timestamp']
            dt = datetime.strptime(timestamp_str, '%d/%b/%Y:%H:%M:%S %z')
            data['datetime'] = dt
            data['date'] = dt.date().isoformat()
            data['hour'] = dt.hour
        except ValueError:
            return None

        # Anonymize IP
        data['ip_hash'] = self.anonymize_ip(data['ip'])
        del data['ip']  # Remove original IP

        # Parse status and size
        data['status'] = int(data['status'])
        data['size'] = int(data['size'])

        # Clean referrer
        if data['referrer'] == '-':
            data['referrer'] = None
        else:
            # Extract domain from referrer
            try:
                parsed = urlparse(data['referrer'])
                data['referrer_domain'] = parsed.netloc
            except:
                data['referrer_domain'] = None

        # Parse user agent for bot detection
        user_agent = data['user_agent'].lower()
        data['is_bot'] = any(bot in user_agent for bot in [
            'bot', 'crawler', 'spider', 'scraper', 'curl', 'wget'
        ])

        return data

    def analyze_logs(self, log_lines: List[str], start_date: str = None, end_date: str = None) -> Dict:
        """
        Analyze log lines and generate statistics.

        Args:
            log_lines: Raw log lines from server
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)

        Returns:
            Dictionary of analytics data
        """
        print("Analyzing logs...")

        parsed_entries = []
        for line in log_lines:
            if not line.strip():
                continue

            entry = self.parse_log_line(line)
            if entry:
                # Filter by date range if specified
                if start_date and entry['date'] < start_date:
                    continue
                if end_date and entry['date'] > end_date:
                    continue

                parsed_entries.append(entry)

        print(f"Parsed {len(parsed_entries)} valid log entries")

        if not parsed_entries:
            return {"error": "No valid log entries found"}

        # Analytics calculations
        analytics = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "period_start": min(e['date'] for e in parsed_entries),
                "period_end": max(e['date'] for e in parsed_entries),
                "total_requests": len(parsed_entries),
                "anonymization": "IP addresses hashed (SHA-256)",
                "privacy": "No PII collected"
            }
        }

        # Daily statistics
        daily_stats = defaultdict(lambda: {
            'requests': 0,
            'unique_visitors': set(),
            'page_views': 0,
            'bandwidth_bytes': 0
        })

        # Path statistics
        path_stats = Counter()
        status_codes = Counter()
        referrer_domains = Counter()
        hourly_distribution = Counter()

        for entry in parsed_entries:
            date = entry['date']

            # Skip bots for visitor counts
            if not entry['is_bot']:
                daily_stats[date]['requests'] += 1
                daily_stats[date]['unique_visitors'].add(entry['ip_hash'])
                daily_stats[date]['bandwidth_bytes'] += entry['size']

                # Count successful requests to HTML pages as page views
                if entry['status'] == 200 and (
                    entry['path'].endswith('.html') or
                    entry['path'].endswith('/') or
                    entry['path'] == '/'
                ):
                    daily_stats[date]['page_views'] += 1
                    path_stats[entry['path']] += 1

            status_codes[entry['status']] += 1
            hourly_distribution[entry['hour']] += 1

            if entry.get('referrer_domain') and entry['referrer_domain']:
                referrer_domains[entry['referrer_domain']] += 1

        # Convert daily stats to serializable format
        analytics['daily'] = {}
        for date, stats in sorted(daily_stats.items()):
            analytics['daily'][date] = {
                'requests': stats['requests'],
                'unique_visitors': len(stats['unique_visitors']),
                'page_views': stats['page_views'],
                'bandwidth_mb': round(stats['bandwidth_bytes'] / (1024 * 1024), 2)
            }

        # Summary statistics
        total_unique_visitors = len(set(
            entry['ip_hash'] for entry in parsed_entries if not entry['is_bot']
        ))

        analytics['summary'] = {
            'total_unique_visitors': total_unique_visitors,
            'total_page_views': sum(s['page_views'] for s in daily_stats.values()),
            'total_bandwidth_mb': round(
                sum(s['bandwidth_bytes'] for s in daily_stats.values()) / (1024 * 1024), 2
            ),
            'avg_daily_visitors': round(total_unique_visitors / len(daily_stats), 1),
            'avg_daily_page_views': round(
                sum(s['page_views'] for s in daily_stats.values()) / len(daily_stats), 1
            )
        }

        # Top pages (limit to top 20)
        analytics['top_pages'] = [
            {"path": path, "views": count}
            for path, count in path_stats.most_common(20)
        ]

        # Status code distribution
        analytics['status_codes'] = dict(status_codes)

        # Top referrers (limit to top 20, exclude own domain)
        analytics['top_referrers'] = [
            {"domain": domain, "count": count}
            for domain, count in referrer_domains.most_common(20)
            if 'pdoom1.com' not in domain
        ]

        # Hourly traffic distribution (0-23)
        analytics['hourly_distribution'] = {
            str(hour): hourly_distribution.get(hour, 0)
            for hour in range(24)
        }

        return analytics

    def save_analytics(self, analytics: Dict, filename: str):
        """Save analytics data to JSON file."""
        output_path = self.output_dir / filename

        with open(output_path, 'w') as f:
            json.dump(analytics, f, indent=2)

        print(f"Analytics saved to {output_path}")
        return output_path

    def generate_report(self, analytics: Dict) -> str:
        """Generate a human-readable report from analytics data."""
        if "error" in analytics:
            return f"Error: {analytics['error']}"

        report = []
        report.append("=" * 60)
        report.append("  DreamHost Analytics Report")
        report.append("=" * 60)
        report.append("")

        meta = analytics['metadata']
        report.append(f"Period: {meta['period_start']} to {meta['period_end']}")
        report.append(f"Generated: {meta['generated_at']}")
        report.append(f"Total Requests: {meta['total_requests']:,}")
        report.append("")

        summary = analytics['summary']
        report.append("SUMMARY STATISTICS")
        report.append("-" * 60)
        report.append(f"  Total Unique Visitors: {summary['total_unique_visitors']:,}")
        report.append(f"  Total Page Views: {summary['total_page_views']:,}")
        report.append(f"  Total Bandwidth: {summary['total_bandwidth_mb']:,} MB")
        report.append(f"  Avg Daily Visitors: {summary['avg_daily_visitors']}")
        report.append(f"  Avg Daily Page Views: {summary['avg_daily_page_views']}")
        report.append("")

        report.append("TOP PAGES")
        report.append("-" * 60)
        for i, page in enumerate(analytics['top_pages'][:10], 1):
            report.append(f"  {i:2d}. {page['path']:<40} {page['views']:>6} views")
        report.append("")

        report.append("TOP REFERRERS")
        report.append("-" * 60)
        for i, ref in enumerate(analytics['top_referrers'][:10], 1):
            report.append(f"  {i:2d}. {ref['domain']:<40} {ref['count']:>6} hits")
        report.append("")

        report.append("DAILY TRAFFIC")
        report.append("-" * 60)
        for date in sorted(analytics['daily'].keys(), reverse=True)[:14]:  # Last 14 days
            day_stats = analytics['daily'][date]
            report.append(
                f"  {date}  |  "
                f"{day_stats['unique_visitors']:>4} visitors  |  "
                f"{day_stats['page_views']:>5} views  |  "
                f"{day_stats['bandwidth_mb']:>6.1f} MB"
            )

        report.append("")
        report.append("=" * 60)
        report.append(f"Privacy: {meta['anonymization']}")
        report.append("=" * 60)

        return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(
        description="Extract analytics from DreamHost VPS"
    )
    parser.add_argument(
        "--ssh-key",
        default="path/to/pdoom-website-instance.pem",
        help="Path to SSH private key"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to extract (default: 30)"
    )
    parser.add_argument(
        "--month",
        help="Extract specific month (YYYY-MM)"
    )
    parser.add_argument(
        "--output",
        help="Output filename (default: auto-generated)"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print report to console"
    )

    args = parser.parse_args()

    # Initialize extractor
    extractor = AnalyticsExtractor(args.ssh_key)

    # Determine date range
    if args.month:
        # Parse month
        year, month = map(int, args.month.split('-'))
        start_date = datetime(year, month, 1).date().isoformat()

        # Calculate end date (last day of month)
        if month == 12:
            end_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
        else:
            end_date = datetime(year, month + 1, 1).date() - timedelta(days=1)
        end_date = end_date.isoformat()

        output_filename = args.output or f"{args.month}.json"
    else:
        start_date = (datetime.now().date() - timedelta(days=args.days)).isoformat()
        end_date = datetime.now().date().isoformat()
        output_filename = args.output or f"last_{args.days}_days.json"

    # Fetch logs
    log_lines = extractor.fetch_logs(days=args.days)

    if not log_lines:
        print("Error: No logs fetched")
        return 1

    # Analyze
    analytics = extractor.analyze_logs(log_lines, start_date, end_date)

    # Save
    extractor.save_analytics(analytics, output_filename)

    # Generate report
    if args.report or True:  # Always print report
        report = extractor.generate_report(analytics)
        print("\n" + report)

    print(f"\n✅ Analytics extraction complete!")
    return 0


if __name__ == "__main__":
    exit(main())
