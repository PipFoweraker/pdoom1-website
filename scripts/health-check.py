#!/usr/bin/env python3

"""
Comprehensive health check for pdoom1-website deployment
Validates critical files, data integrity, and system dependencies
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional

# This script prints emoji. On Windows the console defaults to cp1252 and the
# first print raises UnicodeEncodeError, aborting the run before any check
# executes. That failure is not academic: the resulting traceback -- which
# names the interpreter's own encodings/cp1252.py -- is what leaked an absolute
# local path into public/data/test-report.json, served publicly from pdoom1.com.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


# POLICY, declared here rather than derived from the cron that writes
# version.json. A window derived from its own writer always agrees with it.
# 7 days is the value this check has always used; it is named now so that
# changing it is a decision someone makes rather than a literal they edit.
VERSION_DATA_MAX_AGE_DAYS = 7

# The status vocabulary, in order of severity. Precedence runs left to right:
# a real failure outranks stale data, stale data outranks an unknown, and an
# unknown ALWAYS outranks a warning or a pass.
#
#   FAIL     something is broken and this run established that
#   STALE    the data is real, readable, and older than the declared window
#   UNKNOWN  this run could not establish something either way
#   WARN     nothing failed, but something is worth a human's eye
#   PASS     everything checked, everything current
#
# The old vocabulary was PASS/FAIL, so "I could not tell" had nowhere to go but
# into PASS -- which is exactly what it did, for 966-day-old data.
STATUS_FAIL = 'FAIL'
STATUS_STALE = 'STALE'
STATUS_UNKNOWN = 'UNKNOWN'
STATUS_WARN = 'WARN'
STATUS_PASS = 'PASS'

# Exit codes. 2 is reserved for "could not run honestly", matching
# verify-deployment.py and the estate's convention.
EXIT_BY_STATUS = {
    STATUS_FAIL: 1,
    STATUS_STALE: 1,
    STATUS_UNKNOWN: 2,
    STATUS_WARN: 1,
    STATUS_PASS: 0,
}


class HealthChecker:
    """Comprehensive health check system for website deployment"""

    def __init__(self) -> None:
        self.results: List[Dict[str, Any]] = []
        self.failed_tests: List[str] = []
        self.warnings: List[str] = []
        # Things this run could not establish either way, and things it
        # established are too old. Both are distinct from `warnings`, which is
        # where the stale-data message used to go to be ignored.
        self.unknowns: List[str] = []
        self.stale: List[str] = []
        self.start_time = datetime.now()
        
        # Define critical paths. Resolved, so rel() below can always compute a
        # repo-relative form.
        self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        self.public_dir = os.path.join(self.base_dir, 'public')
        self.data_dir = os.path.join(self.public_dir, 'data')

    @staticmethod
    def last_segment(value: Any) -> str:
        """Final path component, splitting on BOTH separators on every host.

        `os.path.basename` is host-OS dependent: on POSIX it splits on '/' only, so
        "C:\\Users\\<name>\\...\\version.json" comes back UNCHANGED. This file runs on
        a Linux runner on a 6-hourly cron that commits its output, and the text it
        scrubs is not all locally produced -- exception strings and committed data can
        carry Windows paths from the maintainer's box. Using basename there published
        the whole path while reading as if it had been redacted.
        """
        return re.split(r"[\\/]", str(value).rstrip("\\/"))[-1] or str(value)

    def rel(self, filepath: str) -> str:
        """Repo-relative form of a path, for use in any message we might publish.

        This output has been served publicly from pdoom1.com, and absolute paths
        leaked the maintainer's OS username and local directory layout
        (e.g. "C:\\Users\\<name>\\Documents\\A Local Code\\...") as well as CI
        runner paths. Never interpolate a raw filepath into a result message --
        call this instead.
        """
        try:
            out = os.path.relpath(os.path.abspath(filepath), self.base_dir).replace('\\', '/')
        except (ValueError, TypeError):
            # Different drive on Windows, or a non-path string.
            return self.last_segment(filepath)
        # relpath will happily CLIMB OUT of the repo rather than fail, and what it
        # emits then is the layout above base_dir -- "../../home/runner/work/..." on a
        # runner, "../../Users/<name>/..." on the maintainer's box. That is the exact
        # disclosure this function exists to prevent, and it is not a Windows-only
        # case: only Windows raises ValueError for a foreign drive, so on POSIX a
        # "Z:\..." string climbs instead of falling back. Anything above the root
        # degrades to its last segment.
        if out == '..' or out.startswith('../'):
            return self.last_segment(filepath)
        return out

    # Absolute paths in free text we did not construct (subprocess output,
    # exception strings). Belt and braces alongside rel().
    #
    # A directory segment MAY CONTAIN SPACES. The previous pattern used
    # `[^\s'"]+` for the whole tail, which stops dead at the first space -- so
    # "C:\Users\gday\Documents\A Local Code\pdoom1-website\..." matched only as far
    # as "...\Documents\A" and the scrubbed message still read
    # "A Local Code\pdoom1-website\public\data\version.json". That is the maintainer's
    # directory layout, and it is literally the path CLAUDE.md quotes as the leak
    # this guard was written for. The guard was inert against its own founding case.
    #
    # So: consume whole segments (spaces allowed, quotes and newlines not) as long as
    # each is followed by a separator, then a final space-free component. The segment
    # loop only extends across further separators, so ordinary prose after a path
    # ("C:\a\b.json failed at line 3") is not swallowed, and a relative path
    # ("public/data/version.json") never matches at all. {0,64} bounds the segment so
    # a pathological string cannot make this backtrack for a long time.
    _ABS_PATH = re.compile(
        r"([A-Za-z]:[\\/](?:[^\\/'\"\r\n]{0,64}[\\/])*[^\s'\"\\/\r\n]*"
        r"|/(?:home|Users|root|mnt|var/folders)/(?:[^/'\"\r\n]{0,64}/)*[^\s'\"/\r\n]*)")

    @classmethod
    def scrub(cls, text: str) -> str:
        """Replace any absolute path in arbitrary text with its last segment.

        The pattern deliberately matches BOTH a Windows drive path and a POSIX home
        path regardless of which host is running, so the replacement has to be
        host-independent too -- see last_segment().
        """
        return cls._ABS_PATH.sub(lambda m: cls.last_segment(m.group(0)), str(text))

    def log_result(self, test_name: str, passed: bool, message: str = "", is_warning: bool = False) -> None:
        """Log a test result.

        EVERY message is scrubbed here, at the one place they all pass through,
        rather than at each call site. That is deliberate. rel() and scrub() were
        added after absolute paths reached pdoom1.com, and each caller was expected
        to remember to use them -- but four `except Exception as e:` handlers
        interpolated the raw exception string instead (`f"Error reading {shown}:
        {e}"`, `f"Error testing script: {e}"`, and two more), and an OSError's str()
        embeds the absolute path it failed on. The redaction was therefore only as
        good as the last person to remember it, in a file whose output is committed
        by a 6-hourly cron and served publicly.
        A chokepoint cannot be forgotten by a handler written next year.
        """
        message = self.scrub(message)
        test_name = self.scrub(test_name)
        if is_warning:
            self.warnings.append(f"{test_name}: {message}")

        result: Dict[str, Any] = {
            'test': test_name,
            'passed': passed,
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'is_warning': is_warning
        }
        
        self.results.append(result)
        
        if not passed and not is_warning:
            self.failed_tests.append(f"{test_name}: {message}")

    def log_stale(self, test_name: str, message: str = "") -> None:
        """Record data that is real and readable but older than its window.

        Deliberately NOT routed through log_result: that would put it in
        failed_tests, and FAIL outranks STALE, so the distinct verdict this file
        just gained would never once be reachable. Stale IS determined -- we
        know exactly how old it is -- so it counts toward the denominator, which
        is what separates it from an unknown.
        """
        message = self.scrub(message)
        test_name = self.scrub(test_name)
        print(f"\U0001f570️  STALE {test_name}" + (f": {message}" if message else ""))
        self.stale.append(f"{test_name}: {message}")
        self.results.append({
            'test': test_name,
            'passed': False,
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'is_warning': False,
            'is_stale': True,
        })

    def log_unknown(self, test_name: str, message: str = "") -> None:
        """Record something this run could not determine. NOT a pass.

        Goes through log_result so the scrubbing chokepoint above still applies
        -- an unknown's message is usually an exception string, which is exactly
        the shape that put absolute paths on pdoom1.com. Recorded as not-passed
        and not-a-warning would make it a failure, so it carries its own flag and
        is kept out of failed_tests by the is_warning path, then counted here.
        """
        message = self.scrub(message)
        test_name = self.scrub(test_name)
        print(f"? UNKNOWN {test_name}" + (f": {message}" if message else ""))
        self.unknowns.append(f"{test_name}: {message}")
        self.results.append({
            'test': test_name,
            'passed': False,
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'is_warning': False,
            'is_unknown': True,
        })

    def overall_status(self) -> str:
        """Derive the verdict. Severity precedence, never a coin toss."""
        if self.failed_tests:
            return STATUS_FAIL
        if self.stale:
            return STATUS_STALE
        if self.unknowns:
            return STATUS_UNKNOWN
        if self.warnings:
            return STATUS_WARN
        return STATUS_PASS


    def test_file_exists(self, filepath: str, test_name: str) -> bool:
        """Test if a critical file exists"""
        exists = os.path.exists(filepath)
        shown = self.rel(filepath)
        self.log_result(test_name, exists,
                       f"✓ Found: {shown}" if exists else f"✗ Missing: {shown}")
        return exists

    def test_json_valid(self, filepath: str, test_name: str) -> bool:
        """Test if a JSON file is valid"""
        shown = self.rel(filepath)
        try:
            if not os.path.exists(filepath):
                self.log_result(test_name, False, f"File not found: {shown}")
                return False

            with open(filepath, 'r', encoding='utf-8') as f:
                json.load(f)
            self.log_result(test_name, True, f"✓ Valid JSON: {shown}")
            return True
        except json.JSONDecodeError as e:
            self.log_result(test_name, False, f"Invalid JSON: {shown} - {e}")
            return False
        except Exception as e:
            self.log_result(test_name, False, f"Error reading {shown}: {e}")
            return False
    
    def test_script_executable(self, script_path: str, test_name: str) -> bool:
        """Test if a script can be executed"""
        shown = self.rel(script_path)
        try:
            if not os.path.exists(script_path):
                self.log_result(test_name, False, f"Script not found: {shown}")
                return False

            # Test Python script syntax
            result = subprocess.run([sys.executable, '-m', 'py_compile', script_path],
                                  capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace")

            if result.returncode == 0:
                self.log_result(test_name, True, f"✓ Script compiles: {shown}")
                return True
            else:
                # A traceback carries the interpreter's own install path (this is
                # how "C:/Users/<name>/AppData/Local/Programs/Python/..." reached
                # the public site). Report only the final line, path-scrubbed.
                detail = (result.stderr or "").strip().splitlines()
                detail = detail[-1] if detail else "unknown error"
                self.log_result(test_name, False,
                                f"Compilation error in {shown}: {self.scrub(detail)}")
                return False

        except subprocess.TimeoutExpired:
            self.log_result(test_name, False, f"Script compilation timeout: {shown}")
            return False
        except Exception as e:
            self.log_result(test_name, False, f"Error testing script: {e}")
            return False
    
    def test_version_data_integrity(self) -> bool:
        """Test version data structure and content"""
        version_file = os.path.join(self.data_dir, 'version.json')
        
        try:
            if not os.path.exists(version_file):
                self.log_result("Version Data Structure", False, "version.json not found")
                return False
            
            with open(version_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check required fields
            required_fields = ['latest_release', 'repository_stats', 'game_stats', 'last_updated']
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                self.log_result("Version Data Structure", False, 
                              f"Missing fields: {', '.join(missing_fields)}")
                return False
            
            # Check release data
            release = data['latest_release']
            release_fields = ['version', 'name', 'published_at', 'html_url']
            missing_release_fields = [field for field in release_fields if field not in release]
            
            if missing_release_fields:
                self.log_result("Release Data Structure", False,
                              f"Missing release fields: {', '.join(missing_release_fields)}")
                return False
            
            # Check game stats
            game_stats = data['game_stats']
            stats_fields = ['baseline_doom_percent', 'frontier_labs_count', 'strategic_possibilities']
            missing_stats_fields = [field for field in stats_fields if field not in game_stats]
            
            if missing_stats_fields:
                self.log_result("Game Stats Structure", False,
                              f"Missing stats fields: {', '.join(missing_stats_fields)}")
                return False
            
            self.log_result("Version Data Structure", True, "✓ All required fields present")
            
            # AGE IS A HARD INPUT TO THE VERDICT.  D2 of pdoom1-website#384.
            #
            # This block used to log a PASS in all three of its outcomes --
            # fresh, stale, and "could not parse timestamp" -- with the last two
            # carrying is_warning=True. Warnings never reached overall_status,
            # which was `PASS if not failed_tests`. Measured against a 2024
            # timestamp the script returned PASS, 100%, exit 0.
            #
            # Three outcomes now, and only one of them is a pass.
            age_days = None
            raw = data.get('last_updated')
            if raw in (None, ""):
                self.log_unknown("Data Freshness", "version.json has no last_updated")
            else:
                try:
                    last_updated = datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
                    age_days = (datetime.now() - last_updated.replace(tzinfo=None)).days
                except Exception as e:
                    self.log_unknown("Data Freshness", f"Could not parse timestamp: {e}")

            if age_days is not None:
                if age_days < 0:
                    # Not fresh -- a clock disagreement, and we cannot say which
                    # clock is wrong. Absence of a marker is never a clean bill.
                    self.log_unknown(
                        "Data Freshness",
                        f"last_updated is {abs(age_days)} day(s) in the future",
                    )
                elif age_days > VERSION_DATA_MAX_AGE_DAYS:
                    self.log_stale(
                        "Data Freshness",
                        f"version.json is {age_days} days old, "
                        f"window is {VERSION_DATA_MAX_AGE_DAYS}",
                    )
                else:
                    self.log_result("Data Freshness", True, f"✓ Data is {age_days} days old")


            return True
            
        except Exception as e:
            self.log_result("Version Data Structure", False, f"Error validating data: {e}")
            return False
    
    def run_all_checks(self) -> Dict[str, Any]:
        """Run all health checks"""
        print("🏥 Running comprehensive health checks...")
        print("=" * 50)
        
        # Critical file checks
        critical_files = [
            (os.path.join(self.public_dir, 'index.html'), "Main Index File"),
            (os.path.join(self.public_dir, 'config.json'), "Config File"),
            (os.path.join(self.data_dir, 'version.json'), "Version Data"),
            (os.path.join(self.data_dir, 'changes.json'), "Changelog Data"),
        ]
        
        for filepath, name in critical_files:
            self.test_file_exists(filepath, name)
        
        # JSON validation checks
        json_files = [
            (os.path.join(self.public_dir, 'config.json'), "Config JSON"),
            (os.path.join(self.data_dir, 'version.json'), "Version JSON"),
            (os.path.join(self.data_dir, 'changes.json'), "Changes JSON"),
        ]
        
        for filepath, name in json_files:
            if os.path.exists(filepath):
                self.test_json_valid(filepath, name)
        
        # Script validation checks
        script_files = [
            (os.path.join(self.base_dir, 'scripts', 'update-version-info.py'), "Version Update Script"),
            (os.path.join(self.base_dir, 'scripts', 'calculate-game-stats.py'), "Stats Calculation Script"),
        ]
        
        for filepath, name in script_files:
            self.test_script_executable(filepath, name)
        
        # Data integrity checks
        self.test_version_data_integrity()
        
        # Generate summary
        total_tests = len(self.results)
        passed_tests = len([r for r in self.results if r['passed']])
        # THREE buckets, not two. An unknown is not a pass and it is not a
        # failure; folding it into either is the defect this file is being
        # repaired for. success_rate therefore has an explicit denominator: the
        # things that were actually determined. A run where everything was
        # unknown reports 0 determined, not 100%.
        unknown_tests = len([r for r in self.results if r.get('is_unknown')])
        stale_tests = len([r for r in self.results if r.get('is_stale')])
        failed_count = total_tests - passed_tests - unknown_tests - stale_tests
        # STALE counts as determined -- we know exactly how old it is. UNKNOWN
        # does not. That difference is the whole reason they are two states.
        determined = passed_tests + failed_count + stale_tests
        warning_count = len(self.warnings)

        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()

        summary = {
            'timestamp': end_time.isoformat(),
            'duration_seconds': duration,
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': failed_count,
            'unknown_tests': unknown_tests,
            'stale_tests': stale_tests,
            'warnings': warning_count,
            'success_rate': (passed_tests / determined * 100) if determined > 0 else 0,
            'determined_tests': determined,
            'overall_status': self.overall_status(),
            'results': self.results,
            'failed_test_details': self.failed_tests,
            'unknown_details': self.unknowns,
            'stale_details': self.stale,
            'warnings_details': self.warnings
        }
        
        # Save results to file
        results_file = os.path.join(self.data_dir, 'health-check-results.json')
        os.makedirs(self.data_dir, exist_ok=True)
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        
        return summary
    
    def print_summary(self, summary: Dict[str, Any]) -> None:
        """Print a human-readable summary"""
        print("\n" + "=" * 50)
        print("🏥 HEALTH CHECK SUMMARY")
        print("=" * 50)
        
        status_emoji = {
            STATUS_PASS: "✅",
            STATUS_WARN: "⚠️",
            STATUS_UNKNOWN: "❓",
            STATUS_STALE: "🕰️",
            STATUS_FAIL: "❌",
        }.get(summary['overall_status'], "❌")
        print(f"{status_emoji} Overall Status: {summary['overall_status']}")
        print(f"⏱️  Duration: {summary['duration_seconds']:.2f} seconds")
        # The denominator is named. A rate over things that were DETERMINED,
        # printed beside how many were not, so a run that could establish
        # nothing cannot read as 100%.
        print(f"📊 Success Rate: {summary['success_rate']:.1f}% "
              f"of {summary['determined_tests']} determined")
        print(f"✅ Passed: {summary['passed_tests']}/{summary['total_tests']}")
        if summary.get('unknown_tests'):
            print(f"❓ Could not determine: {summary['unknown_tests']}")
            for item in summary.get('unknown_details', []):
                print(f"   • {item}")
        for item in summary.get('stale_details', []):
            print(f"🕰️  STALE: {item}")
        
        if summary['failed_tests'] > 0:
            print(f"❌ Failed: {summary['failed_tests']}")
            print("\n🚨 FAILED TESTS:")
            for failure in summary['failed_test_details']:
                print(f"   • {failure}")
        
        if summary['warnings'] > 0:
            print(f"\n⚠️  Warnings: {summary['warnings']}")
            print("⚠️  WARNING DETAILS:")
            for warning in summary['warnings_details']:
                print(f"   • {warning}")
        
        print(f"\n📄 Full results saved to: public/data/health-check-results.json")
        print("=" * 50)


def main() -> None:
    """Main execution function"""
    checker = HealthChecker()
    summary = checker.run_all_checks()
    checker.print_summary(summary)
    
    # Exit on the verdict, not on a two-way guess. 2 means "could not run
    # honestly" and is deliberately distinct from 1, "something is wrong":
    # a caller that treats non-zero as bad keeps working, and a caller that
    # wants to tell an outage from a defect now can.
    sys.exit(EXIT_BY_STATUS.get(summary['overall_status'], 1))


if __name__ == '__main__':
    main()