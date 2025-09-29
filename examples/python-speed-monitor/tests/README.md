# Speed Monitor Tests

This directory contains test scenarios for the Speed Monitor SDV user function.

## Test Files

- **integration.yaml** - Full integration tests covering all requirements
- **unit.yaml** - Quick unit tests for specific functionality

## Running Tests

### Using the SDV test framework:

```bash
# From the test framework directory
./run-tests.sh \
  --image sdv-speed-monitor:latest \
  --test examples/python-speed-monitor/tests/integration.yaml

# With custom speed limit
./run-tests.sh \
  --image sdv-speed-monitor:latest \
  --test examples/python-speed-monitor/tests/unit.yaml \
  --env SPEED_LIMIT=100
```

### In CI/CD:

```yaml
# Example GitHub Actions step
- name: Run integration tests
  run: |
    ./run-tests.sh \
      --image ${{ env.IMAGE_NAME }}:${{ github.sha }} \
      --test tests/integration.yaml
```

## Requirements Coverage

| Requirement | Test Case | File |
|------------|-----------|------|
| REQ-SPEED-001 | NormalSpeedTest | integration.yaml |
| REQ-SPEED-002 | HighSpeedAlert | integration.yaml |
| REQ-SPEED-003 | SpeedRecovery | integration.yaml |
| REQ-BOUNDARY-001 | BoundaryTest | unit.yaml |
| REQ-ZERO-001 | ZeroSpeedTest | unit.yaml |

## Writing New Tests

When adding new test cases:

1. Use descriptive test names
2. Link to requirements
3. Include both positive and negative cases
4. Test edge cases and boundaries
5. Keep tests independent

Example:
```yaml
- name: NewTestCase
  description: What this test validates
  requirements:
    - REQ-NEW-001
  steps:
    - description: Setup step
      inject:
        path: Vehicle.Speed
        value: 50.0
    - wait: 1.0
    - description: Verify behavior
      expect_log:
        pattern: "Expected output"
```