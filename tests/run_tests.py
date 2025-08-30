#!/usr/bin/env python3
"""
Test runner for Video Frame Extraction System
"""

import unittest
import sys
import os
from io import StringIO

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Test discovery and execution
def run_all_tests():
    """Run all tests and return results"""
    
    # Discover and run tests
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(__file__)
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    # Run tests with detailed output
    stream = StringIO()
    runner = unittest.TextTestRunner(
        stream=stream,
        verbosity=2,
        descriptions=True,
        failfast=False
    )
    
    print("🧪 Running Video Frame Extraction System Tests...\n")
    print("=" * 70)
    
    # Execute tests
    result = runner.run(suite)
    
    # Print results to console
    output = stream.getvalue()
    print(output)
    
    # Summary
    print("=" * 70)
    print(f"📊 TEST SUMMARY:")
    print(f"   Tests run: {result.testsRun}")
    print(f"   Failures: {len(result.failures)}")
    print(f"   Errors: {len(result.errors)}")
    print(f"   Skipped: {len(result.skipped)}")
    
    if result.wasSuccessful():
        print("✅ ALL TESTS PASSED!")
        return True
    else:
        print("❌ SOME TESTS FAILED!")
        
        # Print failure details
        if result.failures:
            print("\n💥 FAILURES:")
            for test, traceback in result.failures:
                print(f"   - {test}: {traceback.split('AssertionError:')[-1].strip()}")
        
        if result.errors:
            print("\n🚨 ERRORS:")
            for test, traceback in result.errors:
                print(f"   - {test}: {traceback.split('Exception:')[-1].strip()}")
        
        return False

def run_specific_test(test_module):
    """Run a specific test module"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(test_module)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

def run_with_coverage():
    """Run tests with coverage report"""
    try:
        import coverage
        
        cov = coverage.Coverage(source=['../app'])
        cov.start()
        
        success = run_all_tests()
        
        cov.stop()
        cov.save()
        
        print("\n📈 COVERAGE REPORT:")
        print("-" * 50)
        cov.report()
        
        # Generate HTML coverage report
        cov.html_report(directory='../coverage_html')
        print(f"\n📋 HTML coverage report generated in: coverage_html/")
        
        return success
        
    except ImportError:
        print("⚠️  Coverage package not installed. Install with: pip install coverage")
        return run_all_tests()

if __name__ == '__main__':
    # Parse command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == '--coverage':
            success = run_with_coverage()
        elif sys.argv[1].startswith('test_'):
            success = run_specific_test(sys.argv[1])
        elif sys.argv[1] == '--help':
            print("Usage:")
            print("  python run_tests.py              # Run all tests")
            print("  python run_tests.py --coverage   # Run with coverage report")
            print("  python run_tests.py test_models  # Run specific test module")
            print("  python run_tests.py --help       # Show this help")
            sys.exit(0)
        else:
            print(f"Unknown argument: {sys.argv[1]}")
            sys.exit(1)
    else:
        success = run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)