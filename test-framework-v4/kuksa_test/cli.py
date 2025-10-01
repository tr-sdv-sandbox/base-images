#!/usr/bin/env python3
"""
Command-line interface for KUKSA Test Framework v4
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from .parser import SpecParser, TestParser
from .runner import TestRunner
from .reporter import TestReporter


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="KUKSA Test Framework v4 - Run VFF-based test suites"
    )
    
    # Required arguments
    parser.add_argument(
        "test_file",
        type=Path,
        help="Test suite YAML file"
    )
    
    # Optional arguments
    parser.add_argument(
        "-s", "--spec",
        type=Path,
        help="VFF specification file (overrides spec in test file)"
    )
    
    parser.add_argument(
        "-k", "--kuksa-url",
        default="127.0.0.1:55556",
        help="KUKSA databroker URL (default: %(default)s)"
    )
    
    parser.add_argument(
        "--token",
        help="KUKSA authentication token"
    )
    
    parser.add_argument(
        "-p", "--process",
        nargs="+",
        help="Command to start application under test"
    )
    
    parser.add_argument(
        "-l", "--log-file",
        type=Path,
        help="Log file to monitor for state transitions"
    )
    
    parser.add_argument(
        "-f", "--format",
        choices=["console", "json", "markdown", "junit"],
        default="console",
        help="Report format (default: %(default)s)"
    )
    
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Output file for report"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--stop-on-failure",
        action="store_true",
        help="Stop test execution on first failure"
    )
    
    parser.add_argument(
        "--filter",
        help="Filter test cases by name pattern"
    )
    
    parser.add_argument(
        "--tag",
        action="append",
        help="Run only tests with specified tags"
    )
    
    parser.add_argument(
        "-c", "--container",
        help="Container name to monitor for logs (or use CONTAINER_NAME env var)"
    )
    
    parser.add_argument(
        "--log-dir",
        type=Path,
        help="Directory for saving detailed test logs"
    )
    
    parser.add_argument(
        "--console-log-level",
        choices=["INFO", "DEBUG"],
        default="INFO",
        help="Console log level (default: %(default)s)"
    )
    
    parser.add_argument(
        "--no-container-logs",
        action="store_true",
        help="Disable interleaving container logs in output"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Load test suite
    try:
        print(f"Loading test suite: {args.test_file}")
        suite = TestParser.from_file(args.test_file)
        
        # Override stop on failure
        if args.stop_on_failure:
            suite.metadata['stop_on_failure'] = True
            
    except Exception as e:
        print(f"Error loading test suite: {e}")
        sys.exit(1)
        
    # Load specification
    spec = None
    spec_file = args.spec or suite.system_spec
    
    if spec_file:
        try:
            # Resolve relative path
            if not Path(spec_file).is_absolute():
                spec_file = args.test_file.parent / spec_file
                
            print(f"Loading VFF specification: {spec_file}")
            spec = SpecParser.from_file(spec_file)
            
        except Exception as e:
            print(f"Error loading specification: {e}")
            sys.exit(1)
    else:
        print("Warning: No VFF specification provided")
        
    # Filter test cases
    if args.filter:
        original_count = len(suite.test_cases)
        suite.test_cases = [
            tc for tc in suite.test_cases 
            if args.filter.lower() in tc.name.lower()
        ]
        print(f"Filtered to {len(suite.test_cases)}/{original_count} test cases")
        
    if args.tag:
        original_count = len(suite.test_cases)
        suite.test_cases = [
            tc for tc in suite.test_cases
            if any(tag in tc.tags for tag in args.tag)
        ]
        print(f"Filtered to {len(suite.test_cases)}/{original_count} test cases by tags")
        
    # Create test runner
    import os
    container_name = args.container or os.environ.get('CONTAINER_NAME')
    
    runner = TestRunner(
        spec=spec,
        kuksa_url=args.kuksa_url,
        kuksa_token=args.token,
        process_command=args.process,
        log_file=args.log_file,
        container_name=container_name,
        log_dir=args.log_dir,
        console_log_level=args.console_log_level,
        capture_container_logs=not args.no_container_logs
    )
    
    # Run tests
    async def run_tests():
        """Async test execution"""
        await runner.setup()
        
        try:
            report = await runner.run_suite(suite)
            return report
        finally:
            await runner.teardown()
            
    try:
        print("\nStarting test execution...")
        print("=" * 60)
        
        report = asyncio.run(run_tests())
        
        # Generate report
        report_content = TestReporter.generate_report(
            report,
            format=args.format,
            output=args.output
        )
        
        # Print to console if no output file or console format
        if not args.output or args.format == "console":
            print(report_content)
            
        # Exit with appropriate code
        summary = report.get_summary()
        if summary['failed'] > 0 or summary['error'] > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\nTest execution interrupted by user")
        sys.exit(130)
        
    except Exception as e:
        print(f"\nTest execution failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()