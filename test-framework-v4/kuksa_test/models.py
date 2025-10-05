"""
Data models for Vehicle Function Framework (VFF) v2 and test specifications.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Union
from datetime import datetime


class SignalType(Enum):
    """VSS signal types"""
    SIGNAL = "signal"      # Sensor data
    ACTUATOR = "actuator"  # Controllable component
    ATTRIBUTE = "attribute"  # Configuration/constant


class SignalDirection(Enum):
    """Signal flow direction relative to Vehicle Service"""
    INPUT = "input"    # Read by Vehicle Service
    OUTPUT = "output"  # Written by Vehicle Service


class ActuatorMode(Enum):
    """Actuator value modes"""
    TARGET = "target"  # Commanded/requested value
    ACTUAL = "actual"  # Physical/achieved value


class RequirementType(Enum):
    """EARS requirement types"""
    UBIQUITOUS = "ubiquitous"  # Simple unconditional
    EVENT_DRIVEN = "event_driven"  # WHEN trigger THEN action
    STATE_DRIVEN = "state_driven"  # WHILE condition THEN action
    OPTION_ORIENTED = "option_oriented"  # WHERE feature exists
    UNWANTED_BEHAVIOR = "unwanted_behavior"  # IF condition THEN prevent
    COMPLEX = "complex"  # Combined conditions
    TEMPORAL = "temporal"  # Time-based constraints
    TEMPORAL_UNWANTED = "temporal_unwanted_behavior"
    TEMPORAL_COMPLEX = "temporal_complex"
    STATE_DRIVEN_TEMPORAL = "state_driven_temporal"


@dataclass
class Signal:
    """VSS signal definition"""
    path: str
    type: SignalType
    datatype: str  # float, int, bool, string, enum
    direction: Optional[SignalDirection] = None
    unit: Optional[str] = None
    min: Optional[Union[int, float]] = None
    max: Optional[Union[int, float]] = None
    mode: Optional[List[ActuatorMode]] = None  # For actuators
    enum_values: Optional[List[str]] = None  # For enum types
    description: Optional[str] = None


@dataclass
class Requirement:
    """System requirement in EARS format"""
    id: str
    text: str
    type: RequirementType
    tags: List[str] = field(default_factory=list)
    verification: Optional[str] = None  # How to verify


@dataclass
class StateTransition:
    """State machine transition"""
    from_state: str
    to_state: str
    trigger: str
    condition: Optional[str] = None  # Expression to evaluate
    action: Optional[str] = None  # Action to perform
    requirements: List[str] = field(default_factory=list)  # Linked requirements


@dataclass
class StateMachine:
    """State machine definition"""
    name: str
    states: List[str]
    initial_state: str
    transitions: List[StateTransition] = field(default_factory=list)
    substates: Dict[str, List[str]] = field(default_factory=dict)  # Hierarchical states


@dataclass
class AutosarInterface:
    """Cross-layer interface definition"""
    name: str
    direction: str  # "vehicle_to_autosar" or "autosar_to_vehicle"
    signals: List[str]  # VSS paths
    description: Optional[str] = None


@dataclass
class VFFSpec:
    """Vehicle Function Framework specification"""
    version: str
    metadata: Dict[str, str]
    signals: Dict[str, Signal] = field(default_factory=dict)  # path -> Signal
    requirements: Dict[str, Requirement] = field(default_factory=dict)  # id -> Requirement
    state_machines: Dict[str, StateMachine] = field(default_factory=dict)  # name -> StateMachine
    autosar_interfaces: List[AutosarInterface] = field(default_factory=list)
    
    def get_signal(self, path: str) -> Optional[Signal]:
        """Get signal by VSS path"""
        return self.signals.get(path)
    
    def get_requirement(self, req_id: str) -> Optional[Requirement]:
        """Get requirement by ID"""
        return self.requirements.get(req_id)
    
    def validate_signal_value(self, path: str, value: Any) -> bool:
        """Validate signal value against specification"""
        signal = self.get_signal(path)
        if not signal:
            return False
            
        # Type validation
        if signal.datatype == "bool" and not isinstance(value, bool):
            return False
        elif signal.datatype in ["float", "double"] and not isinstance(value, (int, float)):
            return False
        elif signal.datatype in ["int", "uint8", "uint16", "uint32"] and not isinstance(value, int):
            return False
        elif signal.datatype == "string" and not isinstance(value, str):
            return False
            
        # Range validation
        if signal.min is not None and value < signal.min:
            return False
        if signal.max is not None and value > signal.max:
            return False
            
        # Enum validation
        if signal.enum_values and value not in signal.enum_values:
            return False
            
        return True


# Test specification models

class TestStepType(Enum):
    """Types of test steps"""
    INJECT = "inject"  # Set signal values
    EXPECT = "expect"  # Verify signal values
    EXPECT_STATE = "expect_state"  # Verify state machine state
    EXPECT_TRANSITION = "expect_transition"  # Verify state machine transition
    WAIT = "wait"  # Time delay
    LOG = "log"  # Log message
    EXPECT_LOG = "expect_log"  # Check container logs
    RUN = "run"  # Execute command


@dataclass
class TestStep:
    """Single test execution step"""
    type: TestStepType
    data: Dict[str, Any]
    timeout: float = 5.0
    description: Optional[str] = None


@dataclass
class TestCase:
    """Test case definition"""
    name: str
    description: Optional[str] = None
    requirements: List[str] = field(default_factory=list)
    setup: List[TestStep] = field(default_factory=list)
    steps: List[TestStep] = field(default_factory=list)
    teardown: List[TestStep] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


class FixtureType(Enum):
    """Types of test fixtures"""
    ACTUATOR_MIRROR = "actuator_mirror"  # TARGET → ACTUAL echo
    SENSOR_GENERATOR = "sensor_generator"  # Generate sensor values
    CUSTOM = "custom"  # Custom Python fixture


@dataclass
class Fixture:
    """Hardware/environment simulation fixture"""
    name: str
    type: FixtureType
    config: Dict[str, Any] = field(default_factory=dict)
    # For actuator_mirror:
    #   - target_signal: str
    #   - actual_signal: str
    #   - delay: float (seconds)
    #   - transform: Optional[str] (e.g., "clamp(0, 100)")
    # For sensor_generator:
    #   - signal: str
    #   - pattern: str (e.g., "sine", "random", "constant")
    #   - params: Dict[str, Any]


@dataclass
class TestSuite:
    """Collection of test cases"""
    name: str
    system_spec: Optional[str] = None  # Path to VFF spec
    fixtures: List[Fixture] = field(default_factory=list)  # Hardware simulation
    setup: List[TestStep] = field(default_factory=list)
    test_cases: List[TestCase] = field(default_factory=list)
    teardown: List[TestStep] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)


# Test execution results

class TestStatus(Enum):
    """Test execution status"""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class StepResult:
    """Result of a single test step"""
    step: TestStep
    status: TestStatus
    message: Optional[str] = None
    actual_value: Optional[Any] = None
    expected_value: Optional[Any] = None
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TestResult:
    """Result of a test case execution"""
    test_case: TestCase
    status: TestStatus
    step_results: List[StepResult] = field(default_factory=list)
    error_message: Optional[str] = None
    duration_ms: float = 0.0
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    
    def add_step_result(self, result: StepResult):
        """Add step result and update overall status"""
        self.step_results.append(result)
        
        # Treat SKIPPED as FAILED for critical verification steps
        if result.step.type in [TestStepType.EXPECT_LOG, TestStepType.EXPECT, TestStepType.EXPECT_STATE]:
            if result.status == TestStatus.SKIPPED:
                result.status = TestStatus.FAILED
                result.message = f"Critical step skipped: {result.message or 'Not implemented'}"
        
        if result.status == TestStatus.FAILED and self.status != TestStatus.ERROR:
            self.status = TestStatus.FAILED
        elif result.status == TestStatus.ERROR:
            self.status = TestStatus.ERROR


@dataclass
class TestReport:
    """Complete test execution report"""
    suite: TestSuite
    spec: Optional[VFFSpec] = None
    results: List[TestResult] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    total_duration_ms: float = 0.0
    
    def get_summary(self) -> Dict[str, int]:
        """Get test execution summary"""
        summary = {
            "total": len(self.results),
            "passed": sum(1 for r in self.results if r.status == TestStatus.PASSED),
            "failed": sum(1 for r in self.results if r.status == TestStatus.FAILED),
            "skipped": sum(1 for r in self.results if r.status == TestStatus.SKIPPED),
            "error": sum(1 for r in self.results if r.status == TestStatus.ERROR),
        }
        return summary
    
    def get_requirements_coverage(self) -> Dict[str, List[str]]:
        """Get requirements coverage mapping"""
        coverage = {}
        for result in self.results:
            for req_id in result.test_case.requirements:
                if req_id not in coverage:
                    coverage[req_id] = []
                coverage[req_id].append(result.test_case.name)
        return coverage