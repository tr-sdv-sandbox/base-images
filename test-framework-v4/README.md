# KUKSA Test Framework v4

A comprehensive test framework that combines the practical features of the existing test framework with the formal specification capabilities of KUKSA Test Tool v3.

## Overview

This framework provides:
- **Vehicle Function Framework (VFF) v2** support for formal specifications
- **State Machine Integration** with our C++ SDK via structured log parsing  
- **Enhanced VSS Signal Handling** with actuator mode support
- **EARS Requirement Format** support for all requirement types
- **Infrastructure-Agnostic Testing** through VSS abstraction
- **Practical Test Features** from existing framework (container logs, etc.)

## Architecture

```
test-framework-v4/
├── README.md
├── requirements.txt
├── setup.py
├── kuksa_test/
│   ├── __init__.py
│   ├── models.py           # VFF data models (signals, requirements, state machines)
│   ├── parser.py           # YAML specification parser
│   ├── runner.py           # Test execution engine
│   ├── reporter.py         # Test result reporting
│   ├── client.py           # Enhanced KUKSA client with actuator support
│   ├── state_tracker.py    # State machine log parser and tracker
│   ├── expression.py       # Expression evaluator for complex conditions
│   └── utils.py            # Utility functions
├── examples/
│   ├── climate_control_spec.yaml    # VFF system specification
│   ├── climate_control_test.yaml    # Test cases
│   └── run_tests.py                 # Example test runner
└── tests/
    └── test_framework.py            # Unit tests
```

## Key Features

### 1. Vehicle Function Framework Support

Define your vehicle function formally:

```yaml
# climate_control_spec.yaml
version: "1.0"
type: "vehicle_function"
metadata:
  name: "Climate Control"
  description: "HVAC control system"

signals:
  - path: "Vehicle.Cabin.HVAC.Station.Row1.Left.Temperature"
    type: "signal"
    datatype: "float"
    direction: "input"
    unit: "celsius"
    
  - path: "Vehicle.Cabin.HVAC.Station.Row1.Left.FanSpeed"
    type: "actuator"
    datatype: "uint8"
    direction: "output"
    mode: ["target", "actual"]
    min: 0
    max: 5

requirements:
  - id: "REQ-CC-001"
    text: "WHEN temperature exceeds target + 2°C THEN system SHALL start cooling"
    type: "event_driven"
    
state_machines:
  - name: "ClimateControl"
    states: ["OFF", "IDLE", "COOLING", "HEATING", "DEFROST", "ECO_MODE", "ERROR"]
    transitions:
      - from: "IDLE"
        to: "COOLING"
        trigger: "start_cooling"
        condition: "temperature_difference > 1.0"
```

### 2. Enhanced Test Cases

```yaml
# climate_control_test.yaml
test_suite:
  name: "Climate Control Tests"
  system_spec: "climate_control_spec.yaml"
  
  test_cases:
    - name: "Normal cooling operation"
      requirements: ["REQ-CC-001"]
      steps:
        - inject:
            "Vehicle.Cabin.HVAC.Station.Row1.Left.Temperature": 28.0
            "Vehicle.Cabin.Infotainment.HMI.TargetTemperature": 22.0
        
        - expect_state:
            machine: "ClimateControl"
            state: "COOLING"
            timeout: 2
            
        - expect:
            "Vehicle.Cabin.HVAC.Station.Row1.Left.FanSpeed": 
              value: "> 0"
              mode: "actual"  # Check actual fan speed
```

### 3. State Machine Integration

The framework automatically:
- Parses state machine logs from C++ applications
- Tracks current state of all state machines
- Verifies state transitions match specifications
- Maps VSS signals to state machine triggers

### 4. Expression Support

Complex conditions in expectations:
```yaml
- expect:
    "Vehicle.Speed": "> 50 and < 120"
    "Vehicle.Powertrain.Range": ">= 100 or Vehicle.Powertrain.FuelSystem.Level > 20"
```

## Usage

### Using Docker (Recommended)

1. **Build the framework:**
   ```bash
   make build
   ```

2. **Run example tests:**
   ```bash
   make example
   ```

3. **Run your own tests:**
   ```bash
   ./run_tests.sh -t your_tests.yaml -s your_spec.yaml -f json -o results/
   ```

### Using Docker Compose

```bash
# Start all services
docker-compose up -d

# Run tests
docker-compose run test-runner python -m kuksa_test.cli \
  /app/examples/climate_control_test.yaml \
  --kuksa-url databroker:55555

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Command Line Interface

```bash
# Basic usage
kuksa-test test_suite.yaml

# With specification
kuksa-test test_suite.yaml --spec vehicle_function.yaml

# Generate JSON report
kuksa-test test_suite.yaml --format json --output report.json

# Filter tests by name
kuksa-test test_suite.yaml --filter "cooling"

# Run tests with specific tags
kuksa-test test_suite.yaml --tag functional --tag safety

# Verbose output
kuksa-test test_suite.yaml --verbose
```

### Python API

```python
from kuksa_test import TestRunner, SpecParser, TestParser

# Load specifications
spec = SpecParser.from_file("climate_control_spec.yaml")
suite = TestParser.from_file("climate_control_test.yaml")

# Create runner
runner = TestRunner(spec=spec, kuksa_url="localhost:55556")

# Run tests
import asyncio

async def run():
    await runner.setup()
    report = await runner.run_suite(suite)
    await runner.teardown()
    return report

report = asyncio.run(run())

# Generate report
from kuksa_test import TestReporter
TestReporter.generate_report(report, format="markdown", output="report.md")
```

## Benefits

1. **Formal Verification**: Validate implementations against formal specifications
2. **State Machine Testing**: Verify complex state-based behaviors
3. **Requirements Traceability**: Track which requirements are covered by tests
4. **Infrastructure Agnostic**: Test against any KUKSA-compatible implementation
5. **Practical Features**: Keep useful features like log checking from existing framework