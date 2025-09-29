# Enhanced Test Framework

This test framework is inspired by KUKSA Test Tool v3 from the COVESA sandbox, providing structured testing with requirements tracking and comprehensive reporting.

## Features

- **YAML-based test definitions**: Clear, readable test specifications
- **Requirements tracking**: Link tests to requirements
- **Signal validation**: Validate signals against VSS specification
- **Structured test steps**: Setup, test cases, and teardown
- **Detailed reporting**: JSON reports with pass/fail status
- **Timeout handling**: Configurable timeouts for each step
- **Actuator support**: Handle TARGET vs ACTUAL for actuators

## Test Specification Format

```yaml
test_suite:
  name: MyTestSuite
  description: Test suite for speed monitoring
  
  setup:
    - description: Initialize test environment
      actions:
        - inject:
            path: Vehicle.Speed
            value: 0
            
  test_cases:
    - name: SpeedLimitTest
      description: Test speed limit detection
      requirements:
        - REQ-SPEED-001
      
      steps:
        - description: Set speed below limit
          inject:
            path: Vehicle.Speed
            value: 100
        
        - wait: 1.0
        
        - description: Verify no alert
          expect:
            path: Vehicle.Speed
            value: 100
            
        - description: Set speed above limit
          inject:
            path: Vehicle.Speed
            value: 130
            
        - wait: 1.0
        
        - description: Verify speed alert triggered
          expect_log:
            pattern: "SPEED ALERT"
            
  teardown:
    - description: Reset environment
      actions:
        - inject:
            path: Vehicle.Speed
            value: 0
```

## Usage

```bash
# Run test suite
python -m test_framework test_suite.yaml

# With custom KUKSA connection
python -m test_framework test_suite.yaml --host kuksa-broker --port 55555

# Generate detailed report
python -m test_framework test_suite.yaml --report results.json

# Validate only (no execution)
python -m test_framework test_suite.yaml --validate-only
```