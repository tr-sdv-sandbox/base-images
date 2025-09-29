#!/usr/bin/env python3
"""
Test runner inspired by KUKSA Test Tool v3
Provides structured testing with YAML specifications
"""
import asyncio
import yaml
import json
import time
import re
import argparse
import subprocess
import threading
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from kuksa_client.grpc import VSSClient
from kuksa_client.grpc import Datapoint


@dataclass
class TestResult:
    """Result of a single test step"""
    step_description: str
    passed: bool
    error_message: Optional[str] = None
    duration: float = 0.0


@dataclass
class TestCaseResult:
    """Result of a complete test case"""
    name: str
    description: str
    requirements: List[str] = field(default_factory=list)
    results: List[TestResult] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0
    
    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


@dataclass
class TestSuiteResult:
    """Result of entire test suite"""
    name: str
    description: str
    test_cases: List[TestCaseResult] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0
    
    @property
    def passed(self) -> bool:
        return all(tc.passed for tc in self.test_cases)
    
    @property
    def total_tests(self) -> int:
        return len(self.test_cases)
    
    @property
    def passed_tests(self) -> int:
        return sum(1 for tc in self.test_cases if tc.passed)


class TestRunner:
    """Runs test suites against KUKSA.val"""
    
    def __init__(self, host: str = "localhost", port: int = 55555, 
                 timeout: float = 10.0, stop_on_failure: bool = False,
                 container_name: str = None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.stop_on_failure = stop_on_failure
        self.container_name = container_name
        self.client = None
        self.logs = []
        self.log_capture_thread = None
        self.stop_log_capture = False
        
    def _capture_logs(self):
        """Capture logs from container in a separate thread"""
        if not self.container_name:
            return
            
        try:
            # Follow logs from container
            process = subprocess.Popen(
                ['docker', 'logs', '-f', self.container_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            while not self.stop_log_capture:
                line = process.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if line:
                    self.logs.append(line)
                    
            process.terminate()
            
        except Exception as e:
            print(f"Error capturing logs: {e}")
    
    async def connect(self):
        """Connect to KUKSA.val databroker"""
        self.client = VSSClient(
            host=self.host,
            port=self.port,
            ensure_startup_connection=False
        )
        self.client.connect()
        print(f"Connected to KUKSA.val at {self.host}:{self.port}")
        
        # Start log capture thread if container name provided
        if self.container_name:
            self.log_capture_thread = threading.Thread(
                target=self._capture_logs,
                daemon=True
            )
            self.log_capture_thread.start()
            print(f"Started log capture for container: {self.container_name}")
        
    async def disconnect(self):
        """Disconnect from KUKSA.val"""
        # Stop log capture
        if self.log_capture_thread:
            self.stop_log_capture = True
            self.log_capture_thread.join(timeout=2.0)
            
        if self.client:
            self.client.disconnect()
            
    async def inject_signal(self, path: str, value: Any) -> bool:
        """Inject a signal value"""
        try:
            datapoint = Datapoint(value)
            self.client.set_current_values({path: datapoint})
            return True
        except Exception as e:
            print(f"Failed to inject {path}={value}: {e}")
            return False
            
    async def expect_signal(self, path: str, expected_value: Any, 
                          tolerance: float = 0.01) -> tuple[bool, str]:
        """Check if signal has expected value"""
        try:
            response = self.client.get_current_values([path])
            if path not in response:
                return False, f"Signal {path} not found"
                
            actual_value = response[path].value
            
            # Handle numeric comparison with tolerance
            if isinstance(expected_value, (int, float)) and isinstance(actual_value, (int, float)):
                if abs(actual_value - expected_value) <= tolerance:
                    return True, f"{path}={actual_value}"
                else:
                    return False, f"Expected {path}={expected_value}, got {actual_value}"
            else:
                if actual_value == expected_value:
                    return True, f"{path}={actual_value}"
                else:
                    return False, f"Expected {path}={expected_value}, got {actual_value}"
                    
        except Exception as e:
            return False, f"Error reading {path}: {e}"
            
    def expect_log(self, pattern: str) -> tuple[bool, str]:
        """Check if log contains pattern"""
        for log in self.logs:
            if re.search(pattern, log):
                return True, f"Found pattern '{pattern}' in logs"
        return False, f"Pattern '{pattern}' not found in logs"
        
    async def execute_step(self, step: Dict[str, Any]) -> TestResult:
        """Execute a single test step"""
        start_time = time.time()
        description = step.get('description', 'Unnamed step')
        
        try:
            # Handle inject action
            if 'inject' in step:
                inject = step['inject']
                success = await self.inject_signal(inject['path'], inject['value'])
                duration = time.time() - start_time
                if success:
                    return TestResult(description, True, duration=duration)
                else:
                    return TestResult(description, False, 
                                    f"Failed to inject {inject['path']}", duration)
                                    
            # Handle wait action
            elif 'wait' in step:
                await asyncio.sleep(step['wait'])
                duration = time.time() - start_time
                return TestResult(description, True, duration=duration)
                
            # Handle expect action
            elif 'expect' in step:
                expect = step['expect']
                passed, message = await self.expect_signal(
                    expect['path'], 
                    expect['value'],
                    expect.get('tolerance', 0.01)
                )
                duration = time.time() - start_time
                return TestResult(description, passed, 
                                None if passed else message, duration)
                                
            # Handle expect_log action
            elif 'expect_log' in step:
                passed, message = self.expect_log(step['expect_log']['pattern'])
                duration = time.time() - start_time
                return TestResult(description, passed, 
                                None if passed else message, duration)
                                
            else:
                return TestResult(description, False, "Unknown step type", 0.0)
                
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(description, False, str(e), duration)
            
    async def execute_test_case(self, test_case: Dict[str, Any]) -> TestCaseResult:
        """Execute a complete test case"""
        result = TestCaseResult(
            name=test_case['name'],
            description=test_case.get('description', ''),
            requirements=test_case.get('requirements', []),
            start_time=time.time()
        )
        
        print(f"\nRunning test case: {result.name}")
        if result.description:
            print(f"  Description: {result.description}")
        if result.requirements:
            print(f"  Requirements: {', '.join(result.requirements)}")
            
        for step in test_case.get('steps', []):
            step_result = await self.execute_step(step)
            result.results.append(step_result)
            
            status = "✓" if step_result.passed else "✗"
            print(f"  {status} {step_result.step_description}")
            if step_result.error_message:
                print(f"    Error: {step_result.error_message}")
                
            if not step_result.passed and self.stop_on_failure:
                print("    Stopping due to failure")
                break
                
        result.end_time = time.time()
        return result
        
    async def execute_actions(self, actions: List[Dict[str, Any]]):
        """Execute a list of actions (for setup/teardown)"""
        for action in actions:
            if 'inject' in action:
                inject = action['inject']
                await self.inject_signal(inject['path'], inject['value'])
            elif 'wait' in action:
                await asyncio.sleep(action['wait'])
                
    async def run_test_suite(self, suite: Dict[str, Any]) -> TestSuiteResult:
        """Run complete test suite"""
        result = TestSuiteResult(
            name=suite['name'],
            description=suite.get('description', ''),
            start_time=time.time()
        )
        
        print(f"\n{'='*60}")
        print(f"Test Suite: {result.name}")
        if result.description:
            print(f"Description: {result.description}")
        print(f"{'='*60}")
        
        # Setup
        if 'setup' in suite:
            print("\nRunning setup...")
            for setup_step in suite['setup']:
                await self.execute_actions(setup_step.get('actions', []))
                
        # Test cases
        for test_case in suite.get('test_cases', []):
            tc_result = await self.execute_test_case(test_case)
            result.test_cases.append(tc_result)
            
        # Teardown
        if 'teardown' in suite:
            print("\nRunning teardown...")
            for teardown_step in suite['teardown']:
                await self.execute_actions(teardown_step.get('actions', []))
                
        result.end_time = time.time()
        
        # Summary
        print(f"\n{'='*60}")
        print(f"Test Summary: {result.passed_tests}/{result.total_tests} passed")
        print(f"Total duration: {result.end_time - result.start_time:.2f}s")
        print(f"Result: {'PASSED' if result.passed else 'FAILED'}")
        print(f"{'='*60}")
        
        return result
        
    def generate_report(self, result: TestSuiteResult) -> Dict[str, Any]:
        """Generate JSON report"""
        return {
            "suite_name": result.name,
            "suite_description": result.description,
            "passed": result.passed,
            "total_tests": result.total_tests,
            "passed_tests": result.passed_tests,
            "duration": result.end_time - result.start_time,
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "test_cases": [
                {
                    "name": tc.name,
                    "description": tc.description,
                    "requirements": tc.requirements,
                    "passed": tc.passed,
                    "duration": tc.duration,
                    "steps": [
                        {
                            "description": step.step_description,
                            "passed": step.passed,
                            "error": step.error_message,
                            "duration": step.duration
                        }
                        for step in tc.results
                    ]
                }
                for tc in result.test_cases
            ]
        }


async def main():
    parser = argparse.ArgumentParser(description='Run KUKSA test suite')
    parser.add_argument('test_spec', help='Path to test specification YAML')
    parser.add_argument('--host', default='localhost', help='KUKSA host')
    parser.add_argument('--port', type=int, default=55555, help='KUKSA port')
    parser.add_argument('--timeout', type=float, default=10.0, help='Default timeout')
    parser.add_argument('--stop-on-failure', action='store_true', 
                        help='Stop test case on first failure')
    parser.add_argument('--report', help='Path to save JSON report')
    parser.add_argument('--validate-only', action='store_true',
                        help='Validate spec without running')
    parser.add_argument('--container', help='Container name to capture logs from')
    parser.add_argument('--verbose', action='store_true',
                        help='Show verbose output')
    
    args = parser.parse_args()
    
    # Load test specification
    with open(args.test_spec, 'r') as f:
        spec = yaml.safe_load(f)
        
    if args.validate_only:
        print("Test specification is valid")
        return
        
    # Run tests
    runner = TestRunner(
        host=args.host,
        port=args.port,
        timeout=args.timeout,
        stop_on_failure=args.stop_on_failure,
        container_name=args.container
    )
    
    try:
        await runner.connect()
        result = await runner.run_test_suite(spec['test_suite'])
        
        if args.report:
            report = runner.generate_report(result)
            with open(args.report, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\nReport saved to: {args.report}")
            
    finally:
        await runner.disconnect()
        
    return 0 if result.passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)