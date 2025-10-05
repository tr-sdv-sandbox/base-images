# Test Framework v5 - C++ Implementation with KUKSA v2 Support

## Overview

A C++ test framework that properly supports KUKSA v2 provider pattern, using the C++ SDK with correct `Actuate()` and `PublishValue()` RPCs.

## Why v5?

The Python v4 framework uses old kuksa-client library with v1 APIs:
- `set_target_values()` - Sets target values directly (v1 pattern)
- Does NOT use `Actuate()` RPC
- Cannot test v2 providers properly

v5 will use our C++ SDK which properly supports v2:
- `client.set_target()` - Uses `Actuate()` RPC
- `client.publish()` - Uses `PublishValue()` RPC
- `client.subscribe()` - Uses `Subscribe()` RPC
- Full v2 provider pattern support

## Architecture

### Components

1. **YAML Parser** (`yaml_parser.hpp/cpp`)
   - Parse test suite YAML files
   - Support same format as v4
   - Use yaml-cpp library

2. **Test Models** (`test_models.hpp`)
   - TestSuite, TestCase, TestStep structures
   - StepType enum (INJECT, EXPECT, WAIT, etc.)
   - ActuatorMode enum (TARGET, ACTUAL)

3. **KUKSA Client Wrapper** (`kuksa_client_wrapper.hpp/cpp`)
   - Wraps SDK VSSClient
   - Handles inject with proper RPC selection:
     - `mode=target` → `client.set_target()` → `Actuate()` RPC
     - `mode=actual/value` → `client.publish()` → `PublishValue()` RPC
   - Handles expect with get/subscribe

4. **Test Runner** (`test_runner.hpp/cpp`)
   - Execute test steps sequentially
   - Track results
   - Generate reports

5. **Main CLI** (`main.cpp`)
   - Parse command line args
   - Load test suite
   - Run tests
   - Output results

### Key Differences from v4

| Feature | v4 (Python) | v5 (C++) |
|---------|-------------|----------|
| Language | Python | C++ |
| KUKSA Client | kuksa-client (v1) | Our SDK (v2) |
| Inject target | `set_target_values()` | `set_target()` → `Actuate()` RPC |
| Inject value | `set_current_values()` | `publish()` → `PublishValue()` RPC |
| Provider support | ❌ No (v1 API) | ✅ Yes (v2 API) |

## Test Step Implementation

### INJECT Step

**v4 Python (broken for v2)**:
```python
if mode == ActuatorMode.TARGET:
    client.set_target_values({path: value})  # v1 API - doesn't work with providers!
```

**v5 C++ (correct for v2)**:
```cpp
if (mode == ActuatorMode::TARGET) {
    Actuator<T> actuator(path);
    client.set_target(actuator, value);  // Uses Actuate() RPC - works with providers!
} else {
    Sensor<T> sensor(path);
    client.publish(sensor, value);  // Uses PublishValue() RPC
}
```

### EXPECT Step

**Both versions similar**:
```cpp
auto value = client.get(sensor);
if (value.has_value() && value.value() == expected) {
    // Pass
}
```

### WAIT Step

```cpp
std::this_thread::sleep_for(std::chrono::milliseconds(duration_ms));
```

## Implementation Plan

### Phase 1: Core Framework
- [x] Design architecture
- [ ] Implement test models (`test_models.hpp`)
- [ ] Implement YAML parser (`yaml_parser.cpp`)
- [ ] Implement KUKSA client wrapper (`kuksa_client_wrapper.cpp`)

### Phase 2: Test Runner
- [ ] Implement test step execution
- [ ] Implement expect/assert logic
- [ ] Add timeout handling
- [ ] Add error reporting

### Phase 3: CLI & Docker
- [ ] Implement main CLI
- [ ] Create Dockerfile
- [ ] Build script
- [ ] Integration with run-tests script

### Phase 4: Testing
- [ ] Test with simple_ac_test.yaml
- [ ] Verify Actuate() RPC works
- [ ] Compare results with v4

## Dependencies

- **yaml-cpp**: YAML parsing
- **sdv-vss**: Our C++ SDK
- **glog**: Logging
- **gRPC/Protobuf**: Already included via SDK

## Docker Image

```dockerfile
FROM sdv-cpp-build:latest AS builder
COPY test-framework-v5 /app/
WORKDIR /app
RUN mkdir build && cd build && cmake .. && make

FROM sdv-cpp-runtime:latest
COPY --from=builder /app/build/test-framework-v5 /usr/local/bin/
CMD ["test-framework-v5"]
```

## Usage

```bash
# Build framework
./test-framework-v5/build.sh

# Run tests (same interface as v4)
./run-tests-v5.sh \
  --image sdv-cpp-climate-control:latest \
  --tests examples/cpp-climate-control/tests/simple_ac_test.yaml
```

## Example Test Suite (Compatible with v4)

```yaml
name: Simple AC Control Test
test_cases:
  - name: AC Activation
    steps:
      - inject:
          path: Vehicle.Cabin.HVAC.IsAirConditioningActive
          value: true
          actuator_mode: target  # v5 will use Actuate() RPC!
      - wait: 1.5s
      - expect:
          path: Vehicle.Private.HVAC.ACRequest
          value: true
```

## Benefits

1. ✅ **Proper KUKSA v2 Support** - Uses Actuate() RPC for providers
2. ✅ **Type Safety** - C++ compile-time checks
3. ✅ **Performance** - Faster execution
4. ✅ **Same Test Format** - Reuse existing YAML test suites
5. ✅ **Better Integration** - Uses same SDK as applications

## Next Steps

1. Implement core data structures
2. Add YAML parsing with yaml-cpp
3. Implement KUKSA client wrapper
4. Build test runner logic
5. Create Docker image
6. Test with existing test suites
