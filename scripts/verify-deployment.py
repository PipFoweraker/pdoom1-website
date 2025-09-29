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

class DeploymentVerifier:
    def __init__(self):
        self.checks_passed = 0
        self.checks_failed = 0
        self.warnings = []
        
    def log_check(self, check_name, passed, message=""):
        """Log a verification check result"""
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} {check_name}" + (f": {message}" if message else ""))
        
        if passed:
            self.checks_passed += 1
        else:
            self.checks_failed += 1
            
    def verify_file_integrity(self):
        """Verify all critical files exist and are valid"""
        print("🔍 Verifying file integrity...")
        
        critical_files = [
            'public/index.html',
            'public/stats/index.html', 
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
                    with open(file_path, 'r') as f:
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
                with open(version_file, 'r') as f:
                    data = json.load(f)
                
                # Check required fields
                required_fields = ['latest_release', 'repository_stats', 'game_stats', 'last_updated']
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_check("Version data structure", False, f"Missing: {missing_fields}")
                else:
                    self.log_check("Version data structure", True, "All fields present")
                
                # Check freshness
                last_updated = datetime.fromisoformat(data['last_updated'])
                age_hours = (datetime.now() - last_updated).total_seconds() / 3600
                
                if age_hours > 24:
                    self.warnings.append(f"Version data is {age_hours:.1f} hours old")
                    self.log_check("Version data freshness", True, f"{age_hours:.1f} hours old (WARNING)")
                else:
                    self.log_check("Version data freshness", True, f"{age_hours:.1f} hours old")
                
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
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS:")
            for warning in self.warnings:
                print(f"  - {warning}")
        
        # Deployment decision
        if self.checks_failed == 0:
            print(f"\n🎉 DEPLOYMENT APPROVED")
            print(f"✅ All verification checks passed. Safe to deploy!")
            return True
        else:
            print(f"\n🚨 DEPLOYMENT BLOCKED")
            print(f"❌ {self.checks_failed} checks failed. Do not deploy!")
            return False
            
    def create_deployment_report(self):
        """Create a deployment readiness report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_checks': self.checks_passed + self.checks_failed,
            'passed': self.checks_passed,
            'failed': self.checks_failed,
            'warnings': self.warnings,
            'deployment_approved': self.checks_failed == 0
        }
        
        report_file = 'public/data/deployment-verification.json'
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        
        with open(report_file, 'w') as f:
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
    deployment_approved = verifier.verify_deployment_readiness()
    
    # Create report
    verifier.create_deployment_report()
    
    # Exit with appropriate code
    if deployment_approved:
        print(f"\n✅ READY FOR DEPLOYMENT")
        sys.exit(0)
    else:
        print(f"\n❌ NOT READY FOR DEPLOYMENT")
        sys.exit(1)

if __name__ == '__main__':
    main()