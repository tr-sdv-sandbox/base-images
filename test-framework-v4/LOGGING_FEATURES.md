# SDV Test Framework v4 - Enhanced Logging Features

The test framework v4 now provides comprehensive logging capabilities that make it easier to debug tests and understand application behavior.

## Features

### 1. **Google Test Style Output**
- Console output mimics Google Test format with `[ RUN ]`, `[ OK ]`, and `[ FAILED ]` markers
- Colored output when running in a terminal
- Test duration shown for each test

### 2. **Container Log Integration**
- Container logs are captured in real-time using a background thread
- Logs are interleaved with test execution steps
- Each log line is prefixed with `[CONTAINER:name]` for clarity

### 3. **Multiple Log Outputs**
- **Console**: Configurable log level (INFO/DEBUG)
- **Per-Test Files**: Each test gets its own log file
- **Suite Log**: Complete log of all tests in the suite

### 4. **Structured Logging**
- Test context is automatically added to all log messages
- Step descriptions are included in debug output
- Container logs preserve their original timestamps

## Usage

### Basic Usage
```bash
./run-tests-v4.sh -i my-image:latest -t tests/integration.yaml
```

### With Enhanced Logging
```bash
./run-tests-v4.sh -i my-image:latest -t tests/integration.yaml \
  --log-dir test-logs \
  --console-log-level DEBUG
```

### Command Line Options
- `--log-dir <path>`: Directory to save detailed test logs
- `--console-log-level <INFO|DEBUG>`: Console verbosity level
- `--no-container-logs`: Disable container log integration

## Log File Structure

When using `--log-dir`, logs are organized as:
```
test-logs/
└── Test_Suite_Name/
    ├── Test_Suite_Name_full.log    # All tests combined
    ├── TestCase1.log               # Individual test log
    ├── TestCase2.log               # Individual test log
    └── ...
```

## Example Output

### Console Output (INFO level)
```
[ RUN      ] NormalEngineOperation
[       OK ] NormalEngineOperation (4006 ms)
[ RUN      ] HighRPMAlert
[       OK ] HighRPMAlert (3005 ms)
```

### Console Output (DEBUG level with container logs)
```
[ RUN      ] HighRPMAlert
  [inject: Set initial RPM] Injected 1 signal(s)
  [CONTAINER:test-subject] I20250930 14:52:55.108124 engine_monitor.cpp:143] RPM: 3000 rpm
  [wait: Wait for system to stabilize] Waited 1.0s
  [inject: Set high RPM] Injected 1 signal(s)
  [CONTAINER:test-subject] I20250930 14:52:56.111196 engine_monitor.cpp:143] RPM: 5000 rpm
  [CONTAINER:test-subject] W20250930 14:52:56.111222 engine_monitor.cpp:145] RPM ALERT: 5000 exceeds limit of 4500
  [expect_log: Check for RPM alert] Found pattern 'RPM ALERT.*5000.*exceeds limit' in logs
[       OK ] HighRPMAlert (3005 ms)
```

### Individual Test Log File
```
2025-09-30 14:52:55,106 [INFO] RUN HighRPMAlert
2025-09-30 14:52:55,108 [DEBUG] [CONTAINER:test-subject-1759243942] I20250930 14:52:55.108072 engine_monitor.cpp:114] Received update with 1 entries
2025-09-30 14:52:55,108 [DEBUG] [CONTAINER:test-subject-1759243942] I20250930 14:52:55.108119 engine_monitor.cpp:119] Processing update for path: Vehicle.Powertrain.CombustionEngine.Speed
2025-09-30 14:52:55,108 [DEBUG] [CONTAINER:test-subject-1759243942] I20250930 14:52:55.108124 engine_monitor.cpp:143] RPM: 3000 rpm
...
```

## Benefits

1. **Debugging**: Easy to see exactly what the application was doing when a test failed
2. **Validation**: Container logs provide proof that the application behaved correctly
3. **Analysis**: Separate log files allow detailed post-test analysis
4. **CI/CD**: Console output is clean at INFO level, detailed logs saved for investigation

## Implementation Details

The logging system uses:
- Python's logging framework with custom formatters
- Threading for real-time container log capture
- Context filters to track test/step execution
- Separate handlers for console and file output

This approach provides the best of both worlds:
- Clean, readable console output for quick feedback
- Detailed logs with container output for thorough analysis
- All logs are properly correlated with test execution