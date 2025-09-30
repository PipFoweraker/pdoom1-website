#!/usr/bin/env python3
"""
Test orchestrator for p(Doom)1 deployment pipeline
Runs all tests in the correct order and provides comprehensive reporting
"""

import os
import sys
import subprocess
import json
import time
from datetime import datetime

class TestOrchestrator:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.test_results = []
        self.start_time = datetime.now()
        
    def log(self, message, level="INFO"):
        """Log a message with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {
            "INFO": "ℹ️ ",
            "SUCCESS": "✅",
            "ERROR": "❌",
            "WARNING": "⚠️ "
        }.get(level, "")
        
        print(f"[{timestamp}] {prefix} {message}")
        
        if self.verbose:
            print()  # Extra line spacing in verbose mode
            
    def run_command(self, command, test_name, timeout=60):
        """Run a command and capture results"""
        self.log(f"Running: {test_name}")
        
        try:
            start_time = time.time()
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=timeout,
                cwd=os.path.dirname(os.path.dirname(__file__))  # Project root
            )
            end_time = time.time()
            
            duration = end_time - start_time
            success = result.returncode == 0
            
            test_result = {
                'test_name': test_name,
                'command': command,
                'success': success,
                'duration': duration,
                'timestamp': datetime.now().isoformat(),
                'stdout': result.stdout,
                'stderr': result.stderr,
                'return_code': result.returncode
            }
            
            self.test_results.append(test_result)
            
            if success:
                self.log(f"{test_name} completed successfully ({duration:.2f}s)", "SUCCESS")
                if self.verbose and result.stdout:
                    print(f"Output: {result.stdout[:500]}...")
            else:
                self.log(f"{test_name} failed ({duration:.2f}s)", "ERROR")
                if result.stderr:
                    self.log(f"Error: {result.stderr[:200]}...", "ERROR")
                    
            return success
            
        except subprocess.TimeoutExpired:
            self.log(f"{test_name} timed out after {timeout}s", "ERROR")
            self.test_results.append({
                'test_name': test_name,
                'command': command,
                'success': False,
                'duration': timeout,
                'timestamp': datetime.now().isoformat(),
                'stdout': '',
                'stderr': f'Command timed out after {timeout} seconds',
                'return_code': -1
            })
            return False
            
        except Exception as e:
            self.log(f"{test_name} failed with exception: {e}", "ERROR")
            self.test_results.append({
                'test_name': test_name,
                'command': command,
                'success': False,
                'duration': 0,
                'timestamp': datetime.now().isoformat(),
                'stdout': '',
                'stderr': str(e),
                'return_code': -2
            })
            return False
            
    def run_test_suite(self, mode="basic"):
        """Run the complete test suite"""
        self.log("Starting p(Doom)1 Test Suite")
        self.log(f"Mode: {mode}")
        self.log("=" * 50)
        
        # Phase 1: Environment Setup
        self.log("Phase 1: Environment Verification", "INFO")
        setup_tests = [
            ("python --version", "Python Available"),
            ("ls package.json", "Package Config Exists"),
            ("ls public/index.html", "Main Website Exists")
        ]
        
        for command, test_name in setup_tests:
            if not self.run_command(command, test_name):
                self.log("Environment setup failed - aborting", "ERROR")
                return False
                
        # Phase 2: Data Generation and Validation
        self.log("\nPhase 2: Data Generation", "INFO")
        data_tests = [
            ("python scripts/update-version-info.py", "Version Data Update"),
            ("python scripts/calculate-game-stats.py", "Game Stats Calculation")
        ]
        
        for command, test_name in data_tests:
            if not self.run_command(command, test_name):
                self.log("Data generation failed", "WARNING")
                # Continue with tests but note the failure
                
        # Phase 3: Health Checks
        self.log("\nPhase 3: Health Verification", "INFO")
        if not self.run_command("python scripts/health-check.py", "Comprehensive Health Check"):
            self.log("Health checks failed", "ERROR")
            
        # Phase 4: Deployment Verification
        self.log("\nPhase 4: Deployment Readiness", "INFO")
        if not self.run_command("python scripts/verify-deployment.py", "Deployment Verification"):
            self.log("Deployment verification failed", "ERROR")
            
        # Phase 5: Extended Tests (if in full mode)
        if mode == "full":
            self.log("\nPhase 5: Extended Testing", "INFO")
            extended_tests = [
                ("python -m json.tool public/data/version.json", "Version JSON Validation"),
                ("python -m json.tool package.json", "Package JSON Validation"),
                ("grep -q 'p(Doom)1' public/index.html", "Content Verification"),
                ("ls public/game-stats/index.html", "Game Stats Page Exists"),
                ("ls public/monitoring/index.html", "Monitoring Page Exists")
            ]
            
            for command, test_name in extended_tests:
                self.run_command(command, test_name)
                
        # Phase 6: Performance Tests (if in full mode)
        if mode == "full":
            self.log("\nPhase 6: Performance Testing", "INFO")
            perf_tests = [
                ("stat public/index.html", "Main Page Size Check"),
                ("find public -name '*.json' -exec wc -c {} +", "Data File Sizes"),
                ("time python scripts/update-version-info.py", "Version Update Performance")
            ]
            
            for command, test_name in perf_tests:
                self.run_command(command, test_name, timeout=30)
                
        return self.generate_report()
        
    def generate_report(self):
        """Generate comprehensive test report"""
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r['success'])
        failed_tests = total_tests - passed_tests
        
        # Create summary
        self.log("\n" + "=" * 50)
        self.log("TEST SUITE SUMMARY")
        self.log("=" * 50)
        self.log(f"Total Tests: {total_tests}")
        self.log(f"✅ Passed: {passed_tests}")
        self.log(f"❌ Failed: {failed_tests}")
        self.log(f"⏱️  Total Duration: {total_duration:.2f}s")
        self.log(f"🎯 Success Rate: {(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "🎯 Success Rate: 0%")
        
        # Show failed tests
        if failed_tests > 0:
            self.log(f"\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result['success']:
                    self.log(f"  - {result['test_name']}: {result['stderr'][:100]}...")
                    
        # Save detailed report
        report = {
            'summary': {
                'start_time': self.start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'total_duration': total_duration,
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': failed_tests,
                'success_rate': (passed_tests/total_tests*100) if total_tests > 0 else 0
            },
            'test_results': self.test_results
        }
        
        # Save report
        report_file = os.path.join('public', 'data', 'test-report.json')
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
            
        self.log(f"📄 Detailed report saved: {report_file}")
        
        # Return overall success
        success = failed_tests == 0
        if success:
            self.log("🎉 ALL TESTS PASSED!", "SUCCESS")
        else:
            self.log("💥 SOME TESTS FAILED!", "ERROR")
            
        return success

def main():
    """Main test orchestrator entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='p(Doom)1 Test Orchestrator')
    parser.add_argument('--mode', choices=['basic', 'full'], default='basic',
                       help='Test mode: basic (core tests) or full (comprehensive)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    parser.add_argument('--timeout', type=int, default=60,
                       help='Default timeout for tests in seconds')
    
    args = parser.parse_args()
    
    # Change to project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    os.chdir(project_root)
    
    # Run tests
    orchestrator = TestOrchestrator(verbose=args.verbose)
    success = orchestrator.run_test_suite(mode=args.mode)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()