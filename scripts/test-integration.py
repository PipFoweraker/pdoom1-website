#!/usr/bin/env python3
"""
Integration Test Suite for p(Doom)1 Website

This script tests all the integration components between the game
and website systems to ensure everything is working correctly.

Usage:
    python scripts/test-integration.py                    # Run all tests
    python scripts/test-integration.py --leaderboard      # Test leaderboard only
    python scripts/test-integration.py --api              # Test API only
    python scripts/test-integration.py --quick            # Quick smoke tests
"""

import json
import argparse
import sys
import time
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import urllib.request
import urllib.error
import socket
from contextlib import contextmanager


class IntegrationTestSuite:
    """Comprehensive integration test suite for website components."""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.data_dir = self.base_dir / "public" / "data"
        self.leaderboard_file = self.base_dir / "public" / "leaderboard" / "data" / "leaderboard.json"
        
        self.test_results = []
        self.passed = 0
        self.failed = 0
        
    def log_result(self, test_name: str, success: bool, message: str = ""):
        """Log a test result."""
        status = "✅ PASS" if success else "❌ FAIL"
        result = {
            "test": test_name,
            "success": success,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        if success:
            self.passed += 1
        else:
            self.failed += 1
            
        print(f"{status} {test_name}: {message}")
    
    def test_leaderboard_bridge(self) -> bool:
        """Test the leaderboard bridge functionality."""
        print("\n🌉 Testing Leaderboard Bridge...")
        
        # Test 1: Bridge script exists and is executable
        bridge_script = self.base_dir / "scripts" / "export-leaderboard-bridge.py"
        if bridge_script.exists():
            self.log_result("Bridge Script Exists", True, str(bridge_script))
        else:
            self.log_result("Bridge Script Exists", False, "Script file not found")
            return False
        
        # Test 2: Bridge can generate data
        try:
            result = subprocess.run([
                "python", str(bridge_script), "--refresh"
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                self.log_result("Bridge Data Generation", True, "Generated fresh data")
            else:
                self.log_result("Bridge Data Generation", False, f"Exit code: {result.returncode}")
                return False
        except Exception as e:
            self.log_result("Bridge Data Generation", False, str(e))
            return False
        
        # Test 3: Generated data structure is valid
        if self.leaderboard_file.exists():
            try:
                with open(self.leaderboard_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Check required fields
                required_fields = ["meta", "seed", "economic_model", "entries"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if not missing_fields:
                    entry_count = len(data.get("entries", []))
                    self.log_result("Data Structure Valid", True, f"{entry_count} entries")
                else:
                    self.log_result("Data Structure Valid", False, f"Missing: {missing_fields}")
                    return False
                    
            except Exception as e:
                self.log_result("Data Structure Valid", False, str(e))
                return False
        else:
            self.log_result("Data Structure Valid", False, "Leaderboard file not found")
            return False
        
        # Test 4: Bridge validation passes
        try:
            result = subprocess.run([
                "python", str(bridge_script), "--validate"
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                self.log_result("Bridge Validation", True, "Validation passed")
            else:
                self.log_result("Bridge Validation", False, "Validation failed")
                return False
        except Exception as e:
            self.log_result("Bridge Validation", False, str(e))
            return False
        
        return True
    
    def test_api_server(self) -> bool:
        """Test the API server functionality."""
        print("\n🚀 Testing API Server...")
        
        # Test 1: API script exists
        api_script = self.base_dir / "scripts" / "api-server.py"
        if api_script.exists():
            self.log_result("API Script Exists", True, str(api_script))
        else:
            self.log_result("API Script Exists", False, "Script file not found")
            return False
        
        # Test 2: Find free port functionality
        try:
            from scripts.api_server import find_free_port
            free_port = find_free_port(9000)  # Start from 9000 to avoid conflicts
            self.log_result("Port Discovery", True, f"Found port {free_port}")
        except Exception as e:
            self.log_result("Port Discovery", False, str(e))
            return False
        
        # Test 3: API server class can be imported
        try:
            from scripts.api_server import GameIntegrationAPIServer
            server = GameIntegrationAPIServer(port=free_port)
            self.log_result("API Server Import", True, "Server class loaded")
        except Exception as e:
            self.log_result("API Server Import", False, str(e))
            return False
        
        return True
    
    def test_data_consistency(self) -> bool:
        """Test data consistency across the system."""
        print("\n📊 Testing Data Consistency...")
        
        # Test 1: Status data exists
        status_file = self.data_dir / "status.json"
        if status_file.exists():
            try:
                with open(status_file, 'r', encoding='utf-8') as f:
                    status_data = json.load(f)
                    
                game_version = status_data.get("game", {}).get("latestRelease", {}).get("version")
                if game_version:
                    self.log_result("Status Data Valid", True, f"Game version: {game_version}")
                else:
                    self.log_result("Status Data Valid", False, "No game version found")
            except Exception as e:
                self.log_result("Status Data Valid", False, str(e))
        else:
            self.log_result("Status Data Valid", False, "Status file not found")
        
        # Test 2: Version data consistency
        version_file = self.data_dir / "version.json"
        if version_file.exists():
            try:
                with open(version_file, 'r', encoding='utf-8') as f:
                    version_data = json.load(f)
                    
                open_issues = version_data.get("repository_stats", {}).get("open_issues", 0)
                self.log_result("Version Data Valid", True, f"Open issues: {open_issues}")
            except Exception as e:
                self.log_result("Version Data Valid", False, str(e))
        else:
            self.log_result("Version Data Valid", False, "Version file not found")
        
        # Test 3: Leaderboard data freshness
        if self.leaderboard_file.exists():
            try:
                with open(self.leaderboard_file, 'r', encoding='utf-8') as f:
                    leaderboard_data = json.load(f)
                    
                generated_time = leaderboard_data.get("meta", {}).get("generated")
                if generated_time:
                    # Check if data is recent (within last 24 hours)
                    from datetime import datetime, timezone, timedelta
                    
                    generated_dt = datetime.fromisoformat(generated_time.replace('Z', '+00:00'))
                    now = datetime.now(timezone.utc)
                    age = now - generated_dt
                    
                    if age < timedelta(hours=24):
                        self.log_result("Data Freshness", True, f"Age: {age}")
                    else:
                        self.log_result("Data Freshness", False, f"Data too old: {age}")
                else:
                    self.log_result("Data Freshness", False, "No generation timestamp")
            except Exception as e:
                self.log_result("Data Freshness", False, str(e))
        
        return True
    
    def test_file_structure(self) -> bool:
        """Test that all required files and directories exist."""
        print("\n📁 Testing File Structure...")
        
        required_files = [
            "public/index.html",
            "public/leaderboard/index.html",
            "public/data/status.json",
            "scripts/health-check.py",
            "scripts/export-leaderboard-bridge.py",
            "scripts/api-server.py"
        ]
        
        for file_path in required_files:
            full_path = self.base_dir / file_path
            if full_path.exists():
                self.log_result(f"File: {file_path}", True, "Exists")
            else:
                self.log_result(f"File: {file_path}", False, "Missing")
        
        return True
    
    def test_health_check_integration(self) -> bool:
        """Test the health check system."""
        print("\n🏥 Testing Health Check Integration...")
        
        try:
            result = subprocess.run([
                "python", "scripts/health-check.py"
            ], capture_output=True, text=True, timeout=30, cwd=self.base_dir)
            
            if result.returncode == 0:
                # Check if results file was created
                health_results_file = self.data_dir / "health-check-results.json"
                if health_results_file.exists():
                    self.log_result("Health Check Execution", True, "Results file created")
                else:
                    self.log_result("Health Check Execution", False, "No results file")
                    return False
            else:
                self.log_result("Health Check Execution", False, f"Exit code: {result.returncode}")
                return False
        except Exception as e:
            self.log_result("Health Check Execution", False, str(e))
            return False
        
        return True
    
    def run_quick_tests(self) -> bool:
        """Run a quick subset of tests for fast validation."""
        print("🚀 Running Quick Integration Tests...\n")
        
        tests = [
            ("File Structure", self.test_file_structure),
            ("Data Consistency", self.test_data_consistency),
            ("Leaderboard Bridge", self.test_leaderboard_bridge)
        ]
        
        all_passed = True
        for test_name, test_func in tests:
            try:
                result = test_func()
                if not result:
                    all_passed = False
            except Exception as e:
                self.log_result(f"{test_name} Exception", False, str(e))
                all_passed = False
        
        return all_passed
    
    def run_full_tests(self) -> bool:
        """Run the complete test suite."""
        print("🧪 Running Full Integration Test Suite...\n")
        
        tests = [
            ("File Structure", self.test_file_structure),
            ("Data Consistency", self.test_data_consistency),
            ("Health Check Integration", self.test_health_check_integration),
            ("Leaderboard Bridge", self.test_leaderboard_bridge),
            ("API Server", self.test_api_server)
        ]
        
        all_passed = True
        for test_name, test_func in tests:
            try:
                result = test_func()
                if not result:
                    all_passed = False
            except Exception as e:
                self.log_result(f"{test_name} Exception", False, str(e))
                all_passed = False
        
        return all_passed
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive test report."""
        report = {
            "test_run": {
                "timestamp": datetime.now().isoformat(),
                "total_tests": len(self.test_results),
                "passed": self.passed,
                "failed": self.failed,
                "success_rate": (self.passed / len(self.test_results)) * 100 if self.test_results else 0
            },
            "results": self.test_results,
            "status": "PASS" if self.failed == 0 else "FAIL"
        }
        
        # Save report to file
        report_file = self.data_dir / "integration-test-results.json"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        return report
    
    def print_summary(self):
        """Print test summary."""
        print(f"\n{'='*50}")
        print("🧪 INTEGRATION TEST SUMMARY")
        print(f"{'='*50}")
        print(f"Total Tests: {len(self.test_results)}")
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        
        if self.test_results:
            success_rate = (self.passed / len(self.test_results)) * 100
            print(f"📊 Success Rate: {success_rate:.1f}%")
        
        if self.failed == 0:
            print("🎉 ALL TESTS PASSED!")
            print("\n🎯 System is ready for:")
            print("   • Real game data integration")
            print("   • API endpoint usage")
            print("   • Production deployment")
        else:
            print("⚠️  Some tests failed. Check the details above.")
            print("\n🔧 Common fixes:")
            print("   • Run: python scripts/export-leaderboard-bridge.py --refresh")
            print("   • Check file permissions")
            print("   • Verify Python dependencies")


def main():
    """CLI interface for the integration test suite."""
    parser = argparse.ArgumentParser(description="p(Doom)1 Integration Test Suite")
    parser.add_argument("--leaderboard", action="store_true", 
                       help="Test leaderboard integration only")
    parser.add_argument("--api", action="store_true",
                       help="Test API server only")
    parser.add_argument("--quick", action="store_true",
                       help="Run quick smoke tests")
    parser.add_argument("--report", action="store_true",
                       help="Generate detailed JSON report")
    
    args = parser.parse_args()
    
    suite = IntegrationTestSuite()
    
    try:
        if args.leaderboard:
            success = suite.test_leaderboard_bridge()
        elif args.api:
            success = suite.test_api_server()
        elif args.quick:
            success = suite.run_quick_tests()
        else:
            success = suite.run_full_tests()
        
        suite.print_summary()
        
        if args.report:
            report = suite.generate_report()
            print(f"\n📄 Detailed report saved to: {suite.data_dir}/integration-test-results.json")
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()