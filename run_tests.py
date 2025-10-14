#!/usr/bin/env python3
"""
Test runner script for drone_metadata_automation.

This script provides various options for running tests including:
- All tests
- Specific test modules
- Integration tests only
- Unit tests only
"""

import sys
import unittest
import argparse
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))


def run_all_tests():
    """Run all tests in the tests directory."""
    print("🧪 Running all tests...")
    loader = unittest.TestLoader()
    start_dir = Path(__file__).parent / 'tests'
    suite = loader.discover(str(start_dir), pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


def run_specific_test(test_module):
    """Run a specific test module."""
    print(f"🧪 Running tests from module: {test_module}")
    
    try:
        # Import the test module
        if test_module.startswith('tests.'):
            module_name = test_module
        else:
            module_name = f"tests.{test_module}"
        
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromName(module_name)
        
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        return result.wasSuccessful()
    
    except Exception as e:
        print(f"❌ Error running test module {test_module}: {e}")
        return False


def run_airdata_parser_tests():
    """Run only the AirdataParser tests."""
    print("🧪 Running AirdataParser tests...")
    
    try:
        from tests.ingestion.test_airdata_parser import TestAirdataParser
        
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(TestAirdataParser)
        
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        return result.wasSuccessful()
    
    except Exception as e:
        print(f"❌ Error running AirdataParser tests: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description='Run drone metadata automation tests')
    parser.add_argument('--all', action='store_true', help='Run all tests')
    parser.add_argument('--airdata', action='store_true', help='Run AirdataParser tests only')
    parser.add_argument('--module', type=str, help='Run specific test module')
    parser.add_argument('--list', action='store_true', help='List available test modules')
    
    args = parser.parse_args()
    
    if args.list:
        print("📋 Available test modules:")
        print("  - tests.ingestion.test_airdata_parser")
        print("  - tests.ingestion.test_video_metadata_parser")
        print("  - tests.test_models")
        return
    
    success = False
    
    if args.airdata:
        success = run_airdata_parser_tests()
    elif args.module:
        success = run_specific_test(args.module)
    elif args.all:
        success = run_all_tests()
    else:
        # Default: run AirdataParser tests (most relevant after recent fix)
        print("🚀 Running default test suite (AirdataParser)...")
        print("Use --help to see other options")
        print("-" * 50)
        success = run_airdata_parser_tests()
    
    if success:
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()