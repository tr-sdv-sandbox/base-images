# C++ Engine Monitor Example

This example demonstrates how to build a C++ SDV user function using the base image.

## Features

- Monitors engine RPM and temperature
- Alerts when limits are exceeded
- Uses KUKSA.val gRPC API with real protobuf definitions
- Multi-stage Docker build for minimal runtime image

## Build

```bash
docker build -t sdv-engine-monitor:latest .
```

## Build Stages

1. **Builder stage** (554MB): Uses `sdv-cpp-base` with all development tools
2. **Runtime stage** (~100MB): Minimal Debian with only runtime libraries

## Run

```bash
docker run --rm \
  -e KUKSA_ADDRESS=kuksa-databroker \
  -e KUKSA_PORT=55555 \
  -e RPM_LIMIT=4000 \
  -e TEMP_LIMIT=100.0 \
  --network sdv-test \
  sdv-engine-monitor:latest
```

## Environment Variables

- `KUKSA_ADDRESS`: KUKSA.val broker address (default: `kuksa-val-server`)
- `KUKSA_PORT`: KUKSA.val broker port (default: `55555`)
- `RPM_LIMIT`: Maximum engine RPM before alert (default: `4500`)
- `TEMP_LIMIT`: Maximum engine temperature in °C (default: `105.0`)

## Monitored Signals

- `Vehicle.Powertrain.CombustionEngine.Speed` - Engine RPM
- `Vehicle.Powertrain.CombustionEngine.ECT` - Engine Coolant Temperature

## Development

To build locally without Docker:

```bash
mkdir build && cd build
cmake ..
make
./engine_monitor
```

## Testing

The engine monitor can be tested using the signal injector:

```bash
# In the test framework
inject:
  path: Vehicle.Powertrain.CombustionEngine.Speed
  value: 5000  # This will trigger RPM alert

inject:
  path: Vehicle.Powertrain.CombustionEngine.ECT
  value: 110.0  # This will trigger temperature alert
```