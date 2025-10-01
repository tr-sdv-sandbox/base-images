"""
Test execution engine for running VFF-based test cases.
"""

import asyncio
import logging
import subprocess
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

from .models import (
    VFFSpec, TestSuite, TestCase, TestStep, TestStepType,
    TestResult, TestStatus, StepResult, TestReport,
    ActuatorMode
)
from .client import KuksaClient, SyncKuksaClient
from .state_tracker import StateTracker, LogStreamProcessor
from .expression import evaluate_condition
from .parser import SpecParser, TestParser
from .log_formatter import TestLogManager


logger = logging.getLogger(__name__)


class TestRunner:
    """
    Main test execution engine.
    
    Features:
    - Execute test cases with VFF specification validation
    - Track state machine transitions via log parsing
    - Support complex expressions in expectations
    - Handle actuator target/actual modes
    - Generate detailed test reports
    """
    
    def __init__(self, 
                 spec: Optional[VFFSpec] = None,
                 kuksa_url: str = "127.0.0.1:55556",
                 kuksa_token: Optional[str] = None,
                 process_command: Optional[List[str]] = None,
                 log_file: Optional[str] = None,
                 container_name: Optional[str] = None,
                 log_dir: Optional[str] = None,
                 console_log_level: str = "INFO",
                 capture_container_logs: bool = True):
        """
        Initialize test runner.
        
        Args:
            spec: Vehicle Function Framework specification
            kuksa_url: KUKSA databroker URL
            kuksa_token: Optional authentication token
            process_command: Command to start application under test
            log_file: Optional log file to monitor
            container_name: Container name for log checking
            log_dir: Directory for saving test logs
            console_log_level: Console log level (INFO, DEBUG)
            capture_container_logs: Whether to capture container logs
        """
        self.spec = spec
        self.kuksa_client = KuksaClient(kuksa_url, kuksa_token)
        self.state_tracker = StateTracker()
        self.process_command = process_command
        self.log_file = log_file
        self.container_name = container_name
        
        self._process = None
        self._log_processor = None
        
        # Log capture from container
        self.container_logs = []
        self._log_capture_thread = None
        self._stop_log_capture = False
        
        # Enhanced logging
        self.log_dir = Path(log_dir) if log_dir else None
        self.console_log_level = console_log_level
        self.capture_container_logs = capture_container_logs
        self.log_manager = None
    
    def _capture_container_logs(self):
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
            
            while not self._stop_log_capture:
                line = process.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if line:
                    self.container_logs.append(line)
                    # Use log manager if available
                    if self.log_manager and self.capture_container_logs:
                        self.log_manager.log_container_output(self.container_name, line)
                    else:
                        logger.info(f"[CONTAINER:{self.container_name}] {line}")
                    
            process.terminate()
            
        except Exception as e:
            logger.error(f"Error capturing container logs: {e}")
        
    async def setup(self):
        """Setup test environment"""
        # Connect to KUKSA
        await self.kuksa_client.connect()
        
        # Start application under test if configured
        if self.process_command:
            await self._start_process()
            
        # Start log monitoring if configured
        if self.log_file:
            self._start_log_monitoring()
            
        # Start container log capture if configured
        if self.container_name:
            self._log_capture_thread = threading.Thread(
                target=self._capture_container_logs,
                daemon=True
            )
            self._log_capture_thread.start()
            logger.info(f"Started log capture for container: {self.container_name}")
            
    async def teardown(self):
        """Cleanup test environment"""
        # Stop container log capture
        if self._log_capture_thread:
            self._stop_log_capture = True
            self._log_capture_thread.join(timeout=2.0)
            
        # Stop log monitoring
        if self._log_processor:
            self._log_processor.stop()
            
        # Stop application
        if self._process:
            self._process.terminate()
            self._process.wait(timeout=5)
            
        # Disconnect from KUKSA
        await self.kuksa_client.disconnect()
        
    async def run_suite(self, suite: TestSuite) -> TestReport:
        """Run a complete test suite"""
        # Initialize log manager for this suite
        if self.log_dir:
            self.log_manager = TestLogManager(
                suite_name=suite.name.replace(' ', '_'),
                log_dir=self.log_dir,
                console_level=self.console_log_level,
                capture_container_logs=self.capture_container_logs
            )
        
        logger.info(f"Starting test suite: {suite.name}")
        logger.info("=" * 60)
        logger.info(f"{len(suite.test_cases)} test(s) from {suite.name}")
        
        # Create report
        report = TestReport(suite=suite, spec=self.spec)
        
        try:
            # Run suite setup
            if suite.setup:
                logger.info("Running suite setup")
                await self._run_steps(suite.setup)
                
            # Run test cases
            for test_case in suite.test_cases:
                result = await self.run_test_case(test_case)
                report.results.append(result)
                
                # Stop on first failure if configured
                if result.status == TestStatus.FAILED and suite.metadata.get('stop_on_failure'):
                    logger.warning("Stopping suite execution due to test failure")
                    break
                    
            # Run suite teardown
            if suite.teardown:
                logger.info("Running suite teardown")
                await self._run_steps(suite.teardown)
                
        except Exception as e:
            logger.error(f"Suite execution failed: {e}")
            
        finally:
            report.end_time = datetime.now()
            report.total_duration_ms = (report.end_time - report.start_time).total_seconds() * 1000
            
        return report
        
    async def run_test_case(self, test_case: TestCase) -> TestResult:
        """Run a single test case"""
        # Set up test-specific logging
        if self.log_manager:
            self.log_manager.set_test_context(test_case.name)
            test_logger = self.log_manager.setup_test_logger(test_case.name)
            test_logger.info(f"RUN {test_case.name}")
        else:
            test_logger = logger
            test_logger.info(f"[ RUN      ] {test_case.name}")
        
        result = TestResult(
            test_case=test_case,
            status=TestStatus.PASSED
        )
        
        try:
            # Run setup steps
            if test_case.setup:
                logger.debug("Running test setup")
                for step in test_case.setup:
                    step_result = await self._execute_step(step)
                    result.add_step_result(step_result)
                    if step_result.status != TestStatus.PASSED:
                        result.error_message = "Setup failed"
                        return result
                        
            # Run main steps
            for i, step in enumerate(test_case.steps):
                logger.debug(f"Running step {i+1}/{len(test_case.steps)}")
                step_result = await self._execute_step(step)
                result.add_step_result(step_result)
                
                if step_result.status != TestStatus.PASSED:
                    break
                    
            # Run teardown steps (always run)
            if test_case.teardown:
                logger.debug("Running test teardown")
                for step in test_case.teardown:
                    step_result = await self._execute_step(step)
                    # Don't fail test for teardown failures
                    if result.status == TestStatus.PASSED and step_result.status != TestStatus.PASSED:
                        logger.warning(f"Teardown step failed: {step_result.message}")
                        
        except Exception as e:
            logger.error(f"Test case failed with error: {e}")
            result.status = TestStatus.ERROR
            result.error_message = str(e)
            
        finally:
            result.end_time = datetime.now()
            result.duration_ms = (result.end_time - result.start_time).total_seconds() * 1000
            
            # Log test completion in Google Test style
            if self.log_manager:
                test_logger = logging.getLogger(f"test.{test_case.name}")
                if result.status == TestStatus.PASSED:
                    test_logger.info(f"OK {test_case.name}", extra={'duration_ms': result.duration_ms})
                else:
                    test_logger.info(f"FAILED {test_case.name}", extra={'duration_ms': result.duration_ms})
                self.log_manager.finish_test(test_case.name)
            else:
                if result.status == TestStatus.PASSED:
                    logger.info(f"[       OK ] {test_case.name} ({result.duration_ms:.0f} ms)")
                else:
                    logger.info(f"[  FAILED  ] {test_case.name} ({result.duration_ms:.0f} ms)")
            
        return result
        
    async def _execute_step(self, step: TestStep) -> StepResult:
        """Execute a single test step"""
        start_time = time.time()
        
        # Set step context for logging
        step_desc = f"{step.type.value}: {step.description or ''}"
        if self.log_manager:
            self.log_manager.set_step_context(step_desc)
        
        try:
            if step.type == TestStepType.INJECT:
                return await self._execute_inject(step)
                
            elif step.type == TestStepType.EXPECT:
                return await self._execute_expect(step)
                
            elif step.type == TestStepType.EXPECT_STATE:
                return await self._execute_expect_state(step)
                
            elif step.type == TestStepType.WAIT:
                return await self._execute_wait(step)
                
            elif step.type == TestStepType.LOG:
                return await self._execute_log(step)
                
            elif step.type == TestStepType.EXPECT_LOG:
                return await self._execute_expect_log(step)
                
            elif step.type == TestStepType.RUN:
                return await self._execute_run(step)
                
            else:
                return StepResult(
                    step=step,
                    status=TestStatus.ERROR,
                    message=f"Unknown step type: {step.type}"
                )
                
        except Exception as e:
            logger.error(f"Step execution failed: {e}")
            return StepResult(
                step=step,
                status=TestStatus.ERROR,
                message=str(e),
                duration_ms=(time.time() - start_time) * 1000
            )
            
    async def _execute_inject(self, step: TestStep) -> StepResult:
        """Execute inject step - set signal values"""
        signals = step.data['signals']
        
        # Validate signals against spec
        if self.spec:
            for path, value in signals.items():
                signal = self.spec.get_signal(path)
                if signal:
                    # Handle actuator mode
                    if isinstance(value, dict) and 'value' in value:
                        actual_value = value['value']
                        mode = ActuatorMode(value.get('mode', 'target'))
                    else:
                        actual_value = value
                        mode = None
                        
                    # Validate value
                    if not await self.kuksa_client.validate_signal(signal, actual_value):
                        return StepResult(
                            step=step,
                            status=TestStatus.FAILED,
                            message=f"Invalid value {actual_value} for signal {path}"
                        )
                        
        # Set values
        try:
            await self.kuksa_client.set_values(signals)
            
            return StepResult(
                step=step,
                status=TestStatus.PASSED,
                message=f"Injected {len(signals)} signal(s)"
            )
            
        except Exception as e:
            return StepResult(
                step=step,
                status=TestStatus.FAILED,
                message=f"Failed to inject signals: {e}"
            )
            
    async def _execute_expect(self, step: TestStep) -> StepResult:
        """Execute expect step - verify signal values"""
        expectations = step.data['expectations']
        timeout = step.timeout
        
        # Wait for expectations to be met
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            all_passed = True
            failures = []
            
            for path, expected in expectations.items():
                try:
                    # Handle actuator mode
                    mode = None
                    if isinstance(expected, dict) and 'value' in expected:
                        expected_value = expected['value']
                        mode = ActuatorMode(expected.get('mode', 'actual'))
                    else:
                        expected_value = expected
                        
                    # Get actual value
                    signal_value = await self.kuksa_client.get_value(path, mode)
                    actual_value = signal_value.value
                    
                    # Evaluate expectation
                    passed, desc = evaluate_condition(str(expected_value), actual_value)
                    
                    if not passed:
                        all_passed = False
                        failures.append(f"{path}: {desc}")
                        
                except Exception as e:
                    all_passed = False
                    failures.append(f"{path}: {e}")
                    
            if all_passed:
                return StepResult(
                    step=step,
                    status=TestStatus.PASSED,
                    message=f"All {len(expectations)} expectation(s) met"
                )
                
            # Wait before retry
            await asyncio.sleep(0.1)
            
        # Timeout - return failure
        return StepResult(
            step=step,
            status=TestStatus.FAILED,
            message=f"Expectations not met within {timeout}s: {'; '.join(failures)}"
        )
        
    async def _execute_expect_state(self, step: TestStep) -> StepResult:
        """Execute expect_state step - verify state machine state"""
        machine = step.data['machine']
        expected_state = step.data['state']
        timeout = step.timeout
        
        # Wait for state
        if self.state_tracker.wait_for_state(machine, expected_state, timeout):
            current = self.state_tracker.get_current_state(machine)
            return StepResult(
                step=step,
                status=TestStatus.PASSED,
                message=f"{machine} is in state {current}"
            )
        else:
            current = self.state_tracker.get_current_state(machine)
            return StepResult(
                step=step,
                status=TestStatus.FAILED,
                message=f"{machine} is in state {current}, expected {expected_state}",
                actual_value=current,
                expected_value=expected_state
            )
            
    async def _execute_wait(self, step: TestStep) -> StepResult:
        """Execute wait step - delay execution"""
        duration = step.data['duration']
        await asyncio.sleep(duration)
        
        return StepResult(
            step=step,
            status=TestStatus.PASSED,
            message=f"Waited {duration}s"
        )
        
    async def _execute_log(self, step: TestStep) -> StepResult:
        """Execute log step - output message"""
        message = step.data['message']
        logger.info(f"TEST LOG: {message}")
        
        return StepResult(
            step=step,
            status=TestStatus.PASSED,
            message=f"Logged: {message}"
        )
        
    async def _execute_expect_log(self, step: TestStep) -> StepResult:
        """Execute expect_log step - check logs for pattern"""
        import re
        
        pattern = step.data['pattern']
        timeout = step.data.get('timeout', step.timeout)
        
        if not self.container_name:
            return StepResult(
                step=step,
                status=TestStatus.ERROR,
                message="No container name specified for log checking"
            )
        
        # Wait for pattern in captured logs
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Search through captured logs
            for log in self.container_logs:
                if re.search(pattern, log, re.IGNORECASE):
                    return StepResult(
                        step=step,
                        status=TestStatus.PASSED,
                        message=f"Found pattern '{pattern}' in logs",
                        duration_ms=(time.time() - start_time) * 1000
                    )
            
            # Wait before retry
            await asyncio.sleep(0.5)
        
        # Pattern not found within timeout
        return StepResult(
            step=step,
            status=TestStatus.FAILED,
            message=f"Pattern '{pattern}' not found in container logs within {timeout}s",
            duration_ms=(time.time() - start_time) * 1000
        )
        
    async def _execute_run(self, step: TestStep) -> StepResult:
        """Execute run step - run command"""
        command = step.data['command']
        
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                return StepResult(
                    step=step,
                    status=TestStatus.PASSED,
                    message=f"Command succeeded: {command}"
                )
            else:
                return StepResult(
                    step=step,
                    status=TestStatus.FAILED,
                    message=f"Command failed: {result.stderr}"
                )
                
        except Exception as e:
            return StepResult(
                step=step,
                status=TestStatus.ERROR,
                message=f"Failed to run command: {e}"
            )
            
    async def _run_steps(self, steps: List[TestStep]):
        """Run a list of steps (for setup/teardown)"""
        for step in steps:
            result = await self._execute_step(step)
            if result.status not in [TestStatus.PASSED, TestStatus.SKIPPED]:
                logger.error(f"Step failed: {result.message}")
                raise RuntimeError(f"Step execution failed: {result.message}")
                
    async def _start_process(self):
        """Start the application under test"""
        logger.info(f"Starting process: {' '.join(self.process_command)}")
        self._process = subprocess.Popen(
            self.process_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Start processing output
        self._log_processor = LogStreamProcessor(self.state_tracker)
        self._log_processor.start_async(self._process.stdout)
        
        # Give process time to start
        await asyncio.sleep(1.0)
        
    def _start_log_monitoring(self):
        """Start monitoring log file"""
        # Implementation would tail log file and feed to state tracker
        pass


class TestRunnerSync:
    """Synchronous wrapper for TestRunner"""
    
    def __init__(self, *args, **kwargs):
        self.runner = TestRunner(*args, **kwargs)
        self._loop = asyncio.new_event_loop()
        
    def setup(self):
        """Synchronous setup"""
        self._loop.run_until_complete(self.runner.setup())
        
    def teardown(self):
        """Synchronous teardown"""
        self._loop.run_until_complete(self.runner.teardown())
        
    def run_suite(self, suite: TestSuite) -> TestReport:
        """Synchronous run_suite"""
        return self._loop.run_until_complete(self.runner.run_suite(suite))
        
    def run_test_case(self, test_case: TestCase) -> TestResult:
        """Synchronous run_test_case"""
        return self._loop.run_until_complete(self.runner.run_test_case(test_case))
        
    def __enter__(self):
        self.setup()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.teardown()