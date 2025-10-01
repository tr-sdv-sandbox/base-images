"""
Enhanced logging formatter for test execution with container log integration.
"""

import logging
import sys
from datetime import datetime
from typing import Optional, TextIO
from pathlib import Path


class TestContextFilter(logging.Filter):
    """Add test context to log records"""
    
    def __init__(self):
        super().__init__()
        self.current_test = None
        self.current_step = None
        
    def set_test_context(self, test_name: Optional[str]):
        self.current_test = test_name
        
    def set_step_context(self, step_desc: Optional[str]):
        self.current_step = step_desc
        
    def filter(self, record):
        record.test_name = self.current_test or "SETUP"
        record.step_desc = self.current_step or ""
        return True


class ContainerLogHandler(logging.Handler):
    """Handler that formats container logs with proper context"""
    
    def __init__(self, container_name: str):
        super().__init__()
        self.container_name = container_name
        
    def emit(self, record):
        # Container logs already have timestamps from the application
        # Just add container context
        try:
            msg = f"[CONTAINER:{self.container_name}] {record.getMessage()}"
            print(msg, file=sys.stdout)
            sys.stdout.flush()
        except Exception:
            self.handleError(record)


class GoogleTestStyleFormatter(logging.Formatter):
    """Formatter that mimics Google Test output style"""
    
    # Color codes
    GREEN = '\033[32m'
    RED = '\033[31m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    CYAN = '\033[36m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    def __init__(self, use_color: bool = True):
        super().__init__()
        self.use_color = use_color and sys.stdout.isatty()
        
    def format(self, record):
        # Get test context
        test_name = getattr(record, 'test_name', '')
        step_desc = getattr(record, 'step_desc', '')

        # Format based on log level and context
        if record.levelname == 'INFO':
            msg = record.getMessage()
            if '[ RUN      ]' in msg:
                # Test case starting
                return self._format_test_run_line(msg)
            elif '[       OK ]' in msg:
                # Test case passed
                return self._format_test_ok_line(msg)
            elif '[  FAILED  ]' in msg:
                # Test case failed
                return self._format_test_fail_line(msg)
            else:
                # Regular info - color it green
                return self._format_info(record)

        elif record.levelname == 'DEBUG':
            # Step-level details
            return self._format_debug(record, test_name, step_desc)

        elif record.levelname == 'ERROR':
            return self._format_error(record)

        elif record.levelname == 'WARNING':
            return self._format_warning(record)

        else:
            return super().format(record)
            
    def _format_test_run_line(self, msg):
        """Color the [ RUN ] line green"""
        if self.use_color:
            return msg.replace('[ RUN      ]', f'[ {self.GREEN}RUN{self.RESET}      ]')
        return msg

    def _format_test_ok_line(self, msg):
        """Color the [  OK ] line green"""
        if self.use_color:
            return msg.replace('[       OK ]', f'[       {self.GREEN}OK{self.RESET} ]')
        return msg

    def _format_test_fail_line(self, msg):
        """Color the [ FAILED ] line red"""
        if self.use_color:
            return msg.replace('[  FAILED  ]', f'[  {self.RED}FAILED{self.RESET}  ]')
        return msg
        
    def _format_info(self, record):
        """Format INFO level logs - add timestamp and color green"""
        msg = record.getMessage()
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        timestamp_ms = f"{timestamp},{int(record.msecs):03d}"

        # Special formatting for container logs - keep in cyan
        if "[CONTAINER:" in msg:
            if self.use_color:
                return f"{timestamp_ms} - {record.name} - {self.CYAN}INFO{self.RESET} - {msg}"
            return f"{timestamp_ms} - {record.name} - INFO - {msg}"
        else:
            # Regular INFO logs in green
            if self.use_color:
                return f"{timestamp_ms} - {record.name} - {self.GREEN}INFO{self.RESET} - {msg}"
            return f"{timestamp_ms} - {record.name} - INFO - {msg}"
        
    def _format_debug(self, record, test_name, step_desc):
        # Debug messages are indented and show step context
        prefix = "  "
        if step_desc:
            prefix += f"[{step_desc}] "
        return f"{prefix}{record.getMessage()}"
        
    def _format_error(self, record):
        """Format ERROR level logs - color red"""
        msg = record.getMessage()
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        timestamp_ms = f"{timestamp},{int(record.msecs):03d}"
        if self.use_color:
            return f"{timestamp_ms} - {record.name} - {self.RED}ERROR{self.RESET} - {msg}"
        return f"{timestamp_ms} - {record.name} - ERROR - {msg}"

    def _format_warning(self, record):
        """Format WARNING level logs - color yellow"""
        msg = record.getMessage()
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        timestamp_ms = f"{timestamp},{int(record.msecs):03d}"
        if self.use_color:
            return f"{timestamp_ms} - {record.name} - {self.YELLOW}WARNING{self.RESET} - {msg}"
        return f"{timestamp_ms} - {record.name} - WARNING - {msg}"


class TestLogManager:
    """Manages logging for test execution with multiple outputs"""
    
    def __init__(self, 
                 suite_name: str,
                 log_dir: Optional[Path] = None,
                 console_level: str = "INFO",
                 file_level: str = "DEBUG",
                 capture_container_logs: bool = True):
        """
        Initialize test log manager.
        
        Args:
            suite_name: Name of the test suite
            log_dir: Directory for log files (creates suite_name subdir)
            console_level: Console log level
            file_level: File log level
            capture_container_logs: Whether to interleave container logs
        """
        self.suite_name = suite_name
        self.capture_container_logs = capture_container_logs
        self.test_loggers = {}
        self.context_filter = TestContextFilter()
        
        # Setup console handler with Google Test style
        self.console_handler = logging.StreamHandler(sys.stdout)
        self.console_handler.setLevel(getattr(logging, console_level))
        self.console_handler.setFormatter(GoogleTestStyleFormatter())
        self.console_handler.addFilter(self.context_filter)
        
        # Setup file handlers if log_dir provided
        self.log_dir = None
        self.suite_handler = None
        if log_dir:
            self.log_dir = Path(log_dir) / suite_name
            self.log_dir.mkdir(parents=True, exist_ok=True)
            
            # Suite-level log file (all tests)
            suite_log = self.log_dir / f"{suite_name}_full.log"
            self.suite_handler = logging.FileHandler(suite_log, mode='w')
            self.suite_handler.setLevel(getattr(logging, file_level))
            self.suite_handler.setFormatter(
                logging.Formatter(
                    '%(asctime)s [%(levelname)s] [%(test_name)s] %(message)s'
                )
            )
            self.suite_handler.addFilter(self.context_filter)
            
    def setup_test_logger(self, test_name: str) -> logging.Logger:
        """Create a logger for a specific test case"""
        logger_name = f"test.{test_name}"
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        
        # Clear any existing handlers
        logger.handlers.clear()
        
        # Add console handler
        logger.addHandler(self.console_handler)
        
        # Add suite-level file handler
        if self.suite_handler:
            logger.addHandler(self.suite_handler)
            
        # Add test-specific file handler
        if self.log_dir:
            test_log = self.log_dir / f"{test_name}.log"
            test_handler = logging.FileHandler(test_log, mode='w')
            test_handler.setLevel(logging.DEBUG)
            test_handler.setFormatter(
                logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
            )
            logger.addHandler(test_handler)
            self.test_loggers[test_name] = test_handler
            
        return logger
        
    def set_test_context(self, test_name: Optional[str]):
        """Set current test context for all loggers"""
        self.context_filter.set_test_context(test_name)
        
    def set_step_context(self, step_desc: Optional[str]):
        """Set current step context for all loggers"""
        self.context_filter.set_step_context(step_desc)
        
    def log_container_output(self, container_name: str, line: str):
        """Log container output with proper formatting"""
        if self.capture_container_logs:
            # Log to current test logger
            current_test = self.context_filter.current_test
            if current_test and current_test != "SETUP":
                logger = logging.getLogger(f"test.{current_test}")
            else:
                # Log to main logger during setup
                logger = logging.getLogger("kuksa_test")
                
            # Always log container output at INFO level
            # The container itself controls its verbosity via LOG_LEVEL env var
            logger.info(f"[CONTAINER:{container_name}] {line}")
                
    def finish_test(self, test_name: str):
        """Clean up test-specific resources"""
        if test_name in self.test_loggers:
            self.test_loggers[test_name].close()
            del self.test_loggers[test_name]
            
    def generate_summary(self, results):
        """Generate Google Test style summary"""
        logger = logging.getLogger("kuksa_test")
        logger.info("=" * 60)
        logger.info(f"Test suite: {self.suite_name}")
        logger.info(f"Total tests: {results['total']}")
        logger.info(f"Passed: {results['passed']}")
        logger.info(f"Failed: {results['failed']}")
        logger.info(f"Skipped: {results['skipped']}")
        logger.info(f"Errors: {results['error']}")
        logger.info("=" * 60)
        
        if self.log_dir:
            logger.info(f"Detailed logs saved to: {self.log_dir}")