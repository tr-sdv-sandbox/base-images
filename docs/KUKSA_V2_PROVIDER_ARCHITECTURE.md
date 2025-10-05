# KUKSA v2 Provider Architecture

## Overview

KUKSA Databroker 0.6.0 uses the kuksa.val.v2 API which introduces a **provider model** for actuator ownership. This is a fundamental architectural change from v1 that provides clear ownership semantics and better separation of concerns.

## Key Concepts

### Signal Types and Ownership

| Signal Type | Owner | Write Method | Read Method |
|-------------|-------|--------------|-------------|
| **Sensor** | Provider (hardware/simulator) | `PublishValue` (low freq) or provider stream | `Subscribe` / `GetValue` |
| **Actuator Command** | Consumer (application) | `Actuate` RPC | N/A (commands are transient) |
| **Actuator Actual Value** | Provider (hardware/simulator) | Provider stream `PublishValuesRequest` | `Subscribe` / `GetValue` |
| **Attribute** | Static configuration | `PublishValue` | `GetValue` |

### Provider vs Consumer

**Provider:**
- Owns hardware or simulates hardware behavior
- Registers ownership of actuators via `OpenProviderStream`
- Receives actuation requests from databroker
- Publishes actual values reflecting hardware state
- Examples: Hardware drivers, ECU adapters, test fixtures

**Consumer:**
- Application logic that commands actuators
- Sends actuation requests via `Actuate` RPC
- Subscribes to actual values to monitor hardware state
- Examples: Climate control app, door controller

## v1 vs v2 Comparison

### v1 Architecture (Deprecated)

```
Application                    Fixture/Hardware
    |                               |
    | Set TARGET ────────────────> Subscribe TARGET
    |                               | (hardware delay)
    | Subscribe ACTUAL <────────── Set ACTUAL
    |                               |
```

**Problems:**
- No ownership enforcement
- Anyone can set TARGET or ACTUAL
- Race conditions possible
- Unclear responsibility

### v2 Architecture (Current)

```
Application (Consumer)         Fixture/Hardware (Provider)
    |                               |
    |                               | ProvideActuationRequest
    |                               | (claims ownership)
    |                               |
    | Actuate ─────────────────────> BatchActuateStreamRequest
    |                               | (receives command)
    |                               | (hardware delay)
    | Subscribe <────────────────── PublishValuesRequest
    | (actual value)                | (reports hardware state)
```

**Benefits:**
- Clear ownership (only provider can write actual values)
- Databroker enforces ownership
- Provider receives all actuation requests through stream
- Clean separation: apps command, providers execute

## OpenProviderStream Protocol

The provider stream is a **bidirectional gRPC stream** for provider-databroker communication.

### Provider → Databroker Messages

1. **ProvideActuationRequest** - Claim ownership of actuators
   ```protobuf
   message ProvideActuationRequest {
     repeated SignalID actuator_identifiers = 1;
   }
   ```

2. **PublishValuesRequest** - Publish sensor/actuator actual values
   ```protobuf
   message PublishValuesRequest {
     map<int32, Datapoint> datapoints = 1;  // signal_id -> value
   }
   ```

3. **BatchActuateStreamResponse** - Acknowledge actuation requests
   ```protobuf
   message BatchActuateStreamResponse {
     map<int32, Error> results = 1;  // signal_id -> error (if any)
   }
   ```

### Databroker → Provider Messages

1. **ProvideActuationResponse** - Confirm ownership claim
   ```protobuf
   message ProvideActuationResponse {
     // Empty - success indicated by no error
   }
   ```

2. **BatchActuateStreamRequest** - Send actuation commands to provider
   ```protobuf
   message BatchActuateStreamRequest {
     map<int32, Value> actuations = 1;  // signal_id -> target value
   }
   ```

### Provider Stream Lifecycle

```
1. Provider opens stream: OpenProviderStream()
2. Provider claims actuators: ProvideActuationRequest([signal1, signal2, ...])
3. Databroker confirms: ProvideActuationResponse
4. Loop:
   a. Databroker sends command: BatchActuateStreamRequest({signal1: value1})
   b. Provider executes (simulates hardware delay)
   c. Provider publishes actual: PublishValuesRequest({signal1: actual_value1})
   d. Provider acknowledges: BatchActuateStreamResponse({signal1: OK})
5. Stream remains open for continuous operation
```

## Implementation Architecture

### SDK API Design

The SDK should provide both consumer and provider APIs:

#### Consumer API (Already Implemented)

```cpp
// Command actuator
client.set_target(actuator, value);  // Calls Actuate RPC

// Read actual value
client.subscribe(actuator, callback);  // Subscribe to get updates
client.get(actuator);  // Get current value
```

#### Provider API (To Be Implemented)

```cpp
class ActuatorProvider {
public:
    // Claim ownership of actuators
    void provide_actuators(const std::vector<std::string>& paths);

    // Register callback for actuation requests
    void on_actuate_request(std::function<void(const ActuationRequest&)> callback);

    // Publish actual value after hardware executes
    void publish_actual(const std::string& path, Value value);

    // Start provider stream
    void start();
};
```

### Fixture Runner Architecture

The fixture runner is a **provider** that simulates hardware behavior:

```cpp
class FixtureRunner : public ActuatorProvider {
private:
    struct ActuatorFixture {
        std::string path;
        double delay_seconds;
    };

    std::vector<ActuatorFixture> fixtures_;

public:
    void LoadFixtures(const std::string& config_file) {
        // Parse YAML, extract actuator paths and delays
    }

    void Start() {
        // Register all fixtures as actuators we provide
        std::vector<std::string> paths;
        for (const auto& f : fixtures_) {
            paths.push_back(f.path);
        }
        provide_actuators(paths);

        // Handle actuation requests
        on_actuate_request([this](const ActuationRequest& req) {
            // Find matching fixture
            auto* fixture = find_fixture(req.path);

            // Simulate hardware delay
            std::this_thread::sleep_for(
                std::chrono::duration<double>(fixture->delay_seconds)
            );

            // Publish actual value (mirror the commanded value)
            publish_actual(req.path, req.value);
        });

        // Start provider stream
        start();
    }
};
```

### Climate Control Architecture

The climate control app is a **consumer** that commands actuators:

```cpp
class RemoteClimateControl {
private:
    VSSClient vss_client_;

    // Define actuators we control
    Actuator<bool> ac_actuator_{"Vehicle.Cabin.HVAC.IsAirConditioningActive"};
    Actuator<bool> ac_request_{"Vehicle.Private.HVAC.ACRequest"};

public:
    void handle_ac_request(bool requested) {
        if (requested) {
            // Command the hardware actuator
            vss_client_.set_target(ac_request_, true);  // Calls Actuate RPC
        }
    }

    void subscribe_to_feedback() {
        // Monitor actual hardware state
        vss_client_.on_actual(ac_request_, [](bool actual) {
            // Hardware confirmed the state change
        });
    }
};
```

## YAML Test Specification

The YAML already implicitly declares ownership through fixtures:

```yaml
fixtures:
  - name: "AC Request Hardware Mirror"
    type: "actuator_mirror"
    target_signal: "Vehicle.Private.HVAC.ACRequest"  # Provider owns this
    actual_signal: "Vehicle.Private.HVAC.ACRequest"  # Same signal
    delay: 0.5  # Hardware simulation delay
```

**Semantics:**
- `type: "actuator_mirror"` → Fixture runner is a **provider**
- `target_signal` → Path of actuator to claim ownership
- `actual_signal` → Where to publish actual values (typically same path)
- `delay` → Simulated hardware execution time

### Enhanced YAML (Future)

We could make ownership more explicit:

```yaml
fixtures:
  - name: "AC Request Hardware Mirror"
    type: "actuator_provider"  # More explicit
    provides:  # Explicit ownership declaration
      - path: "Vehicle.Private.HVAC.ACRequest"
        behavior: "mirror"  # Mirror commanded value to actual
        delay: 0.5
```

## Migration Impact

### What Stays The Same
- ✅ Applications use `set_target()` to command (now calls Actuate RPC)
- ✅ Applications use `subscribe()` to monitor actual values
- ✅ YAML test spec structure
- ✅ Climate control application logic

### What Changes
- ⚠️ SDK internals completely rewritten for v2 (done)
- ⚠️ Fixture runner must use provider stream (to do)
- ⚠️ Cannot directly write actual values without being a provider
- ⚠️ Must claim ownership before providing actuators

### Error Cases

**"Provider for vss_id X does not exist"**
- Cause: Application tries to actuate but no provider registered
- Solution: Ensure fixture runner registers ownership before app starts

**"ALREADY_EXISTS if a provider already claimed the ownership"**
- Cause: Two providers try to claim same actuator
- Solution: Only one provider per actuator (enforced by databroker)

## Performance Considerations

### Provider Stream Advantages
- Single persistent connection vs multiple RPCs
- Bi-directional: provider can publish and receive on same stream
- Batched actuation requests
- Lower latency for high-frequency updates

### When to Use PublishValue vs Provider Stream

**Use `PublishValue` (simple RPC):**
- Static attributes (VIN, model name)
- Low-frequency sensors (< 1 Hz)
- One-time initialization

**Use Provider Stream:**
- Actuators (must use)
- High-frequency sensors (> 1 Hz)
- Coordinated updates (multiple signals)

## References

- KUKSA Databroker: https://github.com/eclipse-kuksa/kuksa-databroker
- kuksa.val.v2 Protocol: `/sdk/cpp/protos/kuksa/val/v2/val.proto`
- Provider Documentation: https://github.com/eclipse-kuksa/kuksa-databroker/blob/main/doc/provider.md
