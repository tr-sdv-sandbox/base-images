# KUKSA v2 Provider Pattern - How It Works

## Overview

KUKSA Databroker v2 uses a **provider pattern** where providers claim ownership of signals and manage their lifecycle. This is fundamentally different from v1 where you could directly read/write target and actual values.

## Key Concepts

### 1. Provider Stream (`OpenProviderStream`)

The provider stream is a **bidirectional gRPC stream** used for:
- Claiming ownership of signals (actuators or sensors)
- Receiving actuation requests (for actuators)
- Publishing high-frequency sensor values (for sensors)

**Important**: You must claim signals BEFORE you can use them on the stream.

### 2. Signal Types and Ownership

#### Actuators
- **Provider** = Owns the actuator, receives actuation commands
- **Client** = Sends actuation commands using `Actuate()` RPC

#### Sensors
- **Provider** = Owns the sensor, publishes values
- **Client** = Subscribes to sensor updates using `Subscribe()` RPC

### 3. Two Ways to Claim Ownership

#### Option A: `ProvideActuationRequest` (for Actuators)
```
Provider Stream Flow:
1. Provider opens stream via OpenProviderStream()
2. Provider sends ProvideActuationRequest with actuator paths
3. Databroker responds with ProvideActuationResponse (ownership granted)
4. Provider receives BatchActuateStreamRequest when clients actuate
5. Provider sends BatchActuateStreamResponse (ACK)
```

#### Option B: `ProvideSignalRequest` (for Sensors/Publishing)
```
Provider Stream Flow:
1. Provider opens stream via OpenProviderStream()
2. Provider sends ProvideSignalRequest with signal paths
3. Databroker responds with ProvideSignalResponse (ownership granted)
4. Provider can now send PublishValuesRequest on the stream
5. Databroker responds with PublishValuesResponse ONLY on error (nothing on success)
```

## Critical Discovery: Publishing Requires Signal Ownership

**From the Rust code**: Before a provider can publish values on the provider stream, it MUST:

1. Send `ProvideSignalRequest` to claim the signals
2. Receive confirmation that ownership is granted
3. Only then can `PublishValuesRequest` succeed

If you try to publish without claiming signals first:
```rust
if local_provider_uuid.is_some() {
    // Can publish
} else {
    // Returns error: "Provider has not claimed yet the signals"
    // Stream is ABORTED
}
```

## Two Publishing Methods

### Method 1: Provider Stream Publishing (High-Frequency)
**Use for**: Sensors that need high-frequency updates (e.g., GPS, CAN data)

**Requirements**:
1. Open `OpenProviderStream()`
2. Send `ProvideSignalRequest` to claim signals
3. Send `PublishValuesRequest` with values
4. Databroker returns `PublishValuesResponse` **only on error** (nothing on success)

**Limitation**: Stream remains open for continuous publishing.

### Method 2: Standalone `PublishValue()` RPC (Low-Frequency)
**Use for**: Occasional updates, attributes, or when you don't want to manage a stream

**Requirements**:
1. Call `PublishValue()` RPC directly
2. No need to claim ownership
3. Works for any signal
4. Returns `PublishValueResponse` with status

**Advantage**: Simpler, no stream management, no ownership required.

## Our Implementation

### What We Got Wrong Initially

1. ❌ **Tried to publish on provider stream without claiming signals**
   - Sent `ProvideActuationRequest` (for actuators)
   - Tried to send `PublishValuesRequest` (for publishing)
   - Failed because we didn't send `ProvideSignalRequest` first

2. ❌ **Thought the stream was buggy**
   - Stream closed after publish
   - Actually it was ABORTED because we didn't claim signals for publishing

### Correct Pattern

#### For Actuator Providers (e.g., Fixture Hardware Simulator)

```cpp
// 1. Open provider stream
ActuatorProvider provider(kuksa_address);
provider.connect();

// 2. Claim actuator ownership
provider.provide_actuators({"Vehicle.Private.HVAC.ACRequest"});

// 3. Set up actuation callback
provider.on_actuate_request([](ActuationRequest req) {
    // Simulate hardware delay
    std::this_thread::sleep_for(std::chrono::milliseconds(500));

    // Publish actual value using STANDALONE RPC (not provider stream)
    VSSClient client(kuksa_address);
    client.connect();
    Sensor<bool> sensor("Vehicle.Private.HVAC.ACRequest");
    client.publish(sensor, std::get<bool>(req.value));
});

// 4. Start provider stream (receives actuation requests)
provider.start();
```

#### For Publishing Values

**Option A**: Use standalone `PublishValue()` RPC (simpler)
```cpp
VSSClient client(kuksa_address);
client.connect();

Sensor<bool> sensor("Vehicle.Cabin.HVAC.IsAirConditioningActive");
client.publish(sensor, true);  // Uses PublishValue() RPC
```

**Option B**: Use provider stream (for high-frequency)
```cpp
// NOT YET IMPLEMENTED - Would require:
// 1. Send ProvideSignalRequest to claim signals
// 2. Then send PublishValuesRequest on stream
// 3. Handle PublishValuesResponse on errors only
```

## Architecture Patterns

### Pattern 1: Climate Control App (Actuator Owner + Value Publisher)

```
Climate App:
1. Is PROVIDER for Vehicle.Cabin.HVAC.IsAirConditioningActive (actuator)
   - Uses OpenProviderStream() + ProvideActuationRequest
   - Receives actuation commands from external systems

2. Is CLIENT for Vehicle.Private.HVAC.ACRequest (actuator)
   - Uses Actuate() RPC to command hardware

3. SUBSCRIBES to Vehicle.Private.HVAC.ACRequest (as sensor)
   - Uses Subscribe() RPC to monitor hardware state

4. PUBLISHES Vehicle.Cabin.HVAC.IsAirConditioningActive (as sensor value)
   - Uses standalone PublishValue() RPC
```

### Pattern 2: Hardware Fixture (Actuator Owner + Value Publisher)

```
Fixture:
1. Is PROVIDER for Vehicle.Private.HVAC.ACRequest (actuator)
   - Uses OpenProviderStream() + ProvideActuationRequest
   - Receives actuation commands from climate app

2. PUBLISHES Vehicle.Private.HVAC.ACRequest (actual value)
   - Uses standalone PublishValue() RPC
   - Simulates hardware state after delay
```

## Key Takeaways

1. **Provider Stream ≠ Publishing Stream** (unless you claim signals with ProvideSignalRequest)
   - `ProvideActuationRequest` → Receive actuation commands
   - `ProvideSignalRequest` → Claim signals for publishing on stream
   - These are SEPARATE steps, can't mix them without proper claiming

2. **Standalone PublishValue() is Simpler**
   - No stream management
   - No ownership claiming required
   - Works for occasional updates
   - Use this unless you need high-frequency streaming

3. **Provider Stream Publishing is Complex**
   - Requires ProvideSignalRequest first
   - Returns response only on error
   - Use only for high-frequency sensor data

4. **Actuation and Publishing are Separate**
   - Actuating an actuator doesn't trigger subscriptions
   - Provider must explicitly publish actual values
   - Published values appear as sensor updates to subscribers

## References

- KUKSA Databroker Rust implementation: `databroker/src/grpc/kuksa_val_v2/val.rs`
- Proto definition: `kuksa/val/v2/val.proto`
- Our SDK: `/home/saka/tr-sdv-sandbox/base-images/sdk/cpp/`
