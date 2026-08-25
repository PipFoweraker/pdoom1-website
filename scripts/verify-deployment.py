#!/usr/bin/env python3
"""
Pre-deployment verification script
Tests all systems before deploying to production
"""

import os
import sys
import json
import subprocess
import urllib.request
import urllib.error
from datetime import datetime

# Windows consoles default to cp1252: the first non-ASCII byte written to stdout
# raises UnicodeEncodeError and kills the script before it does any work. No-op
# on UTF-8 platforms. See CLAUDE.md "Environment / tooling".
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# A DEPLOY GATE THAT CANNOT TELL MUST NOT APPROVE.  D3 of pdoom1-website#384.
#
# This script printed "DEPLOYMENT APPROVED" over freshness it could not
# establish: verify_version_data_fresh() logged a PASS with the word WARNING in
# its message when the data was older than a day, warnings never reached the
# verdict, and `checks_failed == 0` was the whole decision. Two outcomes, so
# "I could not tell" had nowhere to go but into the approving one.
#
# It is not a cosmetic defect here in particular, because this script WRITES
# public/data/deployment-verification.json -- the file /monitoring/ renders. It
# manufactures the evidence the card displays.
#
# Three verdicts now. UNVERIFIABLE is a first-class outcome with its own exit
# code, and it is NOT a pass.
VERDICT_APPROVED = "APPROVED"
VERDICT_REFUSED = "REFUSED"
VERDICT_CANNOT_VERIFY = "CANNOT VERIFY"

EXIT_BY_VERDICT = {
    VERDICT_APPROVED: 0,
    VERDICT_REFUSED: 1,
    VERDICT_CANNOT_VERIFY: 2,
}

# POLICY, declared here rather than derived from the cron that writes the file.
# A window derived from the writer always agrees with the writer.
# auto-update-data.yml runs every 6 hours, so 24h is four missed runs: long
# enough that a single transient failure is not a deploy block, short enough
# that a stopped writer is caught the same day.
VERSION_DATA_MAX_AGE_HOURS = 24


class DeploymentVerifier:
    def __init__(self):
        self.checks_passed = 0
        self.checks_failed = 0
        self.warnings = []
        # Things this run could not establish either way. Never a pass, never a
        # failure -- an admission. Kept separate from `warnings`, which is where
        # the old stale-data message went to be ignored.
        self.unverifiable = []

    def log_check(self, check_name, passed, message=""):
        """Log a verification check result"""
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} {check_name}" + (f": {message}" if message else ""))

        if passed:
            self.checks_passed += 1
        else:
            self.checks_failed += 1

    def log_unverifiable(self, check_name, reason):
        """Record something this run could not determine. NOT a pass."""
        print(f"? UNKNOWN {check_name}: {reason}")
        self.unverifiable.append(f"{check_name}: {reason}")

    def verdict(self):
        """APPROVED / REFUSED / CANNOT VERIFY, in that order of precedence.

        A real failure outranks an unknown: if something is definitely broken,
        say so rather than hiding it behind "could not tell". But an unknown
        ALWAYS outranks approval.
        """
        if self.checks_failed > 0:
            return VERDICT_REFUSED
        if self.unverifiable:
            return VERDICT_CANNOT_VERIFY
        return VERDICT_APPROVED


    def verify_file_integrity(self):
        """Verify all critical files exist and are valid"""
        print("🔍 Verifying file integrity...")
        
        critical_files = [
            'public/index.html', 
            'public/game-stats/index.html', 
            'public/data/version.json',
            'package.json'
        ]
        
        for file_path in critical_files:
            if os.path.exists(file_path):
                # Check file isn't empty
                size = os.path.getsize(file_path)
                if size > 0:
                    self.log_check(f"File {file_path}", True, f"{size} bytes")
                else:
                    self.log_check(f"File {file_path}", False, "File is empty")
            else:
                self.log_check(f"File {file_path}", False, "File missing")
                
    def verify_json_validity(self):
        """Verify all JSON files are valid"""
        print("\n🔍 Verifying JSON validity...")
        
        json_files = [
            'public/data/version.json',
            'package.json'
        ]
        
        for file_path in json_files:
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding="utf-8") as f:
                        json.load(f)
                    self.log_check(f"JSON {file_path}", True, "Valid JSON")
                except json.JSONDecodeError as e:
                    self.log_check(f"JSON {file_path}", False, f"Invalid JSON: {e}")
            else:
                self.log_check(f"JSON {file_path}", False, "File not found")
                
    def verify_content_integrity(self):
        """Verify website content has expected elements"""
        print("\n🔍 Verifying content integrity...")
        
        index_file = 'public/index.html'
        if os.path.exists(index_file):
            with open(index_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Check for critical content
            checks = [
                ('p(Doom)1 title', 'p(Doom)1' in content),
                ('AI Safety mention', 'AI Safety' in content),
                ('Navigation menu', 'nav-links' in content),
                ('Stats section', 'stats' in content),
                ('Download button', 'Download' in content),
                ('Version loading script', 'loadVersionInfo' in content)
            ]
            
            for check_name, condition in checks:
                self.log_check(check_name, condition)
        else:
            self.log_check("Content integrity", False, "index.html not found")
            
    def verify_scripts_executable(self):
        """Verify all deployment scripts can run"""
        print("\n🔍 Verifying script executability...")
        
        scripts = [
            'scripts/update-version-info.py',
            'scripts/calculate-game-stats.py',
            'scripts/health-check.py'
        ]
        
        for script_path in scripts:
            if os.path.exists(script_path):
                try:
                    # Test syntax by compiling
                    with open(script_path, 'r', encoding='utf-8') as f:
                        code = f.read()
                    compile(code, script_path, 'exec')
                    self.log_check(f"Script {script_path}", True, "Syntax valid")
                except SyntaxError as e:
                    self.log_check(f"Script {script_path}", False, f"Syntax error: {e}")
                except Exception as e:
                    self.log_check(f"Script {script_path}", False, f"Error: {e}")
            else:
                self.log_check(f"Script {script_path}", False, "Script not found")
                
    def verify_version_data_fresh(self):
        """Verify version data is recent and valid"""
        print("\n🔍 Verifying version data freshness...")
        
        version_file = 'public/data/version.json'
        if os.path.exists(version_file):
            try:
                with open(version_file, 'r', encoding="utf-8") as f:
                    data = json.load(f)
                
                # Check required fields
                required_fields = ['latest_release', 'repository_stats', 'game_stats', 'last_updated']
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_check("Version data structure", False, f"Missing: {missing_fields}")
                else:
                    self.log_check("Version data structure", True, "All fields present")
                
                # Check freshness.
                #
                # Age is a HARD INPUT to the verdict, not a side note. It used to
                # be logged as a PASS with the word WARNING in the message, and
                # warnings were not read by anything -- so 966-day-old data
                # approved a deployment.
                #
                # Three outcomes, matching the three verdicts:
                #   no usable timestamp -> CANNOT VERIFY   (we do not know)
                #   older than the window -> REFUSED       (we know, and it is stale)
                #   inside the window -> PASS
                raw = data.get('last_updated')
                age_hours = None
                if raw in (None, ""):
                    self.log_unverifiable(
                        "Version data freshness",
                        "version.json has no last_updated, so its age cannot be established",
                    )
                else:
                    try:
                        last_updated = datetime.fromisoformat(str(raw))
                        if last_updated.tzinfo is not None:
                            last_updated = last_updated.replace(tzinfo=None)
                        age_hours = (datetime.now() - last_updated).total_seconds() / 3600
                    except (ValueError, TypeError) as exc:
                        self.log_unverifiable(
                            "Version data freshness",
                            f"last_updated {raw!r} is not a timestamp this script can read ({exc})",
                        )

                if age_hours is not None:
                    if age_hours < 0:
                        # A future stamp is not fresh data, it is a clock
                        # disagreement, and we cannot tell which clock is wrong.
                        self.log_unverifiable(
                            "Version data freshness",
                            f"last_updated is {abs(age_hours):.1f} hours in the FUTURE",
                        )
                    elif age_hours > VERSION_DATA_MAX_AGE_HOURS:
                        self.log_check(
                            "Version data freshness",
                            False,
                            f"{age_hours:.1f} hours old, window is {VERSION_DATA_MAX_AGE_HOURS}h",
                        )
                    else:
                        self.log_check(
                            "Version data freshness", True, f"{age_hours:.1f} hours old"
                        )

            except Exception as e:
                self.log_check("Version data", False, f"Error reading: {e}")
        else:
            self.log_check("Version data", False, "version.json not found")
            
    def verify_external_dependencies(self):
        """Verify external dependencies are accessible"""
        print("\n🔍 Verifying external dependencies...")
        
        # Test GitHub API access
        try:
            req = urllib.request.Request('https://api.github.com/repos/PipFoweraker/pdoom1')
            req.add_header('User-Agent', 'pdoom1-deployment-verifier')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read())
                
            self.log_check("GitHub API access", True, f"Repository: {data['name']}")
        except Exception as e:
            self.log_check("GitHub API access", False, f"Error: {e}")
            
    def verify_deployment_readiness(self):
        """Run comprehensive pre-deployment checks"""
        print("🚀 p(Doom)1 Deployment Verification")
        print("=" * 50)
        
        # Run all verification checks
        self.verify_file_integrity()
        self.verify_json_validity()
        self.verify_content_integrity()
        self.verify_scripts_executable()
        self.verify_version_data_fresh()
        self.verify_external_dependencies()
        
        # Summary
        print("\n" + "=" * 50)
        print("📊 Deployment Verification Summary")
        total_checks = self.checks_passed + self.checks_failed
        print(f"Total Checks: {total_checks}")
        print(f"✓ Passed: {self.checks_passed}")
        print(f"✗ Failed: {self.checks_failed}")
        print(f"⚠ Warnings: {len(self.warnings)}")
        
        print(f"? Could not determine: {len(self.unverifiable)}")

        if self.warnings:
            print(f"\n⚠️  WARNINGS:")
            for warning in self.warnings:
                print(f"  - {warning}")

        if self.unverifiable:
            print(f"\n❓ COULD NOT BE DETERMINED:")
            for item in self.unverifiable:
                print(f"  - {item}")

        # Deployment decision -- three verdicts, never two.
        verdict = self.verdict()
        if verdict == VERDICT_APPROVED:
            print(f"\n🎉 DEPLOYMENT APPROVED")
            print(f"✅ All verification checks passed. Safe to deploy!")
        elif verdict == VERDICT_REFUSED:
            print(f"\n🚨 DEPLOYMENT BLOCKED")
            print(f"❌ {self.checks_failed} checks failed. Do not deploy!")
        else:
            print(f"\n❓ CANNOT VERIFY")
            print(f"❌ {len(self.unverifiable)} thing(s) could not be established, listed above.")
            print(f"   Nothing here failed. Nothing here passed either, and a deploy")
            print(f"   gate that cannot tell must not approve. Resolve them or deploy")
            print(f"   deliberately without this gate.")
        return verdict


    def create_deployment_report(self):
        """Create a deployment readiness report"""
        verdict = self.verdict()
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_checks': self.checks_passed + self.checks_failed,
            'passed': self.checks_passed,
            'failed': self.checks_failed,
            'warnings': self.warnings,
            # `verdict` is the field to read. `unverifiable` is what the third
            # state is made of -- an empty list means nothing was unknown, NOT
            # that nothing was checked, because `total_checks` is right there.
            'verdict': verdict,
            'unverifiable': self.unverifiable,
            # KEPT for anything still reading the old boolean, and narrowed:
            # it is true ONLY on APPROVED. Under the old code it was
            # `checks_failed == 0`, which was also true for every run that
            # could not establish freshness at all.
            'deployment_approved': verdict == VERDICT_APPROVED,
        }
        
        report_file = 'public/data/deployment-verification.json'
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        
        with open(report_file, 'w', encoding="utf-8") as f:
            json.dump(report, f, indent=2)
            
        print(f"📄 Deployment report saved: {report_file}")
        return report

def main():
    """Main deployment verification process"""
    verifier = DeploymentVerifier()
    
    # Change to project root directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    os.chdir(project_root)
    
    # Run verification
    verdict = verifier.verify_deployment_readiness()

    # Create report
    verifier.create_deployment_report()

    # Exit codes match the three verdicts: 0 approved, 1 refused, 2 could not
    # tell. A caller that treats non-zero as "do not deploy" keeps working; a
    # caller that wants to distinguish "broken" from "unknown" now can.
    if verdict == VERDICT_APPROVED:
        print(f"\n✅ READY FOR DEPLOYMENT")
    elif verdict == VERDICT_REFUSED:
        print(f"\n❌ NOT READY FOR DEPLOYMENT")
    else:
        print(f"\n❓ READINESS UNKNOWN -- not approved")
    sys.exit(EXIT_BY_VERDICT[verdict])

if __name__ == '__main__':
    main()