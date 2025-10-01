#!/usr/bin/env python3
"""
Example test runner for Climate Control system.

This demonstrates how to:
1. Load VFF specifications and test cases
2. Start the application under test 
3. Run tests with state machine tracking
4. Generate reports in multiple formats
"""

import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from kuksa_test import (
    SpecParser, TestParser, TestRunner, 
    TestReporter, StateTracker
)


def main():
    """Run climate control tests"""
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # File paths
    spec_file = Path(__file__).parent / "climate_control_spec.yaml"
    test_file = Path(__file__).parent / "climate_control_test.yaml"
    
    # Load specifications
    print("Loading VFF specification...")
    spec = SpecParser.from_file(spec_file)
    print(f"  - Loaded {len(spec.signals)} signals")
    print(f"  - Loaded {len(spec.requirements)} requirements")
    print(f"  - Loaded {len(spec.state_machines)} state machines")
    
    # Load test suite
    print("\nLoading test suite...")
    suite = TestParser.from_file(test_file)
    print(f"  - Loaded {len(suite.test_cases)} test cases")
    
    # Validate test suite against spec
    print("\nValidating test suite...")
    # In a full implementation, would validate signal paths and requirements
    
    # Create test runner
    print("\nInitializing test runner...")
    
    # Command to start the climate control application
    # In real usage, this would start the actual C++ application
    process_command = [
        "python3", "-c", 
        """
import time
import sys

# Simulate state machine logs
print('I20250930 12:00:00.000001 12345 climate_control.cpp:100] [SM:ClimateControl] INIT: state=OFF')
sys.stdout.flush()

# Wait for power on
time.sleep(2)
print('I20250930 12:00:02.000001 12345 climate_control.cpp:200] [SM:ClimateControl] TRANSITION: OFF -> IDLE | trigger=power_on')
print('I20250930 12:00:02.000002 12345 climate_control.cpp:201] [SM:ClimateControl] STATE: current=IDLE')
sys.stdout.flush()

# Wait for temperature trigger
time.sleep(2)
print('I20250930 12:00:04.000001 12345 climate_control.cpp:300] [SM:ClimateControl] TRANSITION: IDLE -> COOLING | trigger=start_cooling')
print('I20250930 12:00:04.000002 12345 climate_control.cpp:301] [SM:ClimateControl] STATE: current=COOLING')
sys.stdout.flush()

# Temperature reached
time.sleep(2)
print('I20250930 12:00:06.000001 12345 climate_control.cpp:400] [SM:ClimateControl] TRANSITION: COOLING -> IDLE | trigger=temperature_reached')
print('I20250930 12:00:06.000002 12345 climate_control.cpp:401] [SM:ClimateControl] STATE: current=IDLE')
sys.stdout.flush()

# Keep running
while True:
    time.sleep(1)
"""
    ]
    
    # For this example, we'll use a mock KUKSA connection
    # In real usage, connect to actual KUKSA databroker
    runner = TestRunner(
        spec=spec,
        kuksa_url="127.0.0.1:55556",  # Would be real KUKSA URL
        process_command=process_command if "--with-process" in sys.argv else None
    )
    
    # Run tests
    try:
        print("\nStarting test execution...")
        print("=" * 60)
        
        import asyncio
        
        async def run_tests():
            await runner.setup()
            
            try:
                report = await runner.run_suite(suite)
                return report
            finally:
                await runner.teardown()
        
        # Execute
        if "--mock" in sys.argv:
            # Mock execution for demo
            from kuksa_test.models import TestReport, TestResult, TestStatus
            report = TestReport(suite=suite, spec=spec)
            
            # Simulate test results
            for test_case in suite.test_cases:
                result = TestResult(
                    test_case=test_case,
                    status=TestStatus.PASSED if "Low battery" not in test_case.name else TestStatus.FAILED,
                    duration_ms=1234.5
                )
                report.results.append(result)
                
        else:
            report = asyncio.run(run_tests())
        
        # Generate reports
        print("\nGenerating reports...")
        
        # Console report
        console_report = TestReporter.generate_report(report, format="console")
        print("\n" + console_report)
        
        # Save other formats
        TestReporter.generate_report(
            report, 
            format="json", 
            output="climate_control_report.json"
        )
        
        TestReporter.generate_report(
            report,
            format="markdown",
            output="climate_control_report.md"
        )
        
        TestReporter.generate_report(
            report,
            format="junit",
            output="climate_control_report.xml"
        )
        
        print("\nReports saved:")
        print("  - climate_control_report.json")
        print("  - climate_control_report.md")
        print("  - climate_control_report.xml")
        
        # Exit with appropriate code
        summary = report.get_summary()
        if summary['failed'] > 0 or summary['error'] > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except Exception as e:
        print(f"\nTest execution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()