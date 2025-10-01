# SDV State Machine SDK (C++)

A modern C++ state machine library designed for Software-Defined Vehicle applications with comprehensive observability through structured logging and optional Prometheus metrics.

## Features

- **Type-safe state definitions** using enum classes
- **Hierarchical states** with composite state support
- **Modern C++17** with clean API
- **Thread-safe** state transitions
- **Structured logging** for complete observability
- **Production metrics** via Prometheus (optional)
- **Test-friendly** with parseable log format
- **Header-only** core functionality
- **CMake** integration

## Requirements

- C++17 or later
- CMake 3.16+
- Google glog (for logging)
- yaml-cpp (for configuration)
- Optional: prometheus-cpp (for metrics)

## Installation

### Using CMake FetchContent

```cmake
include(FetchContent)
FetchContent_Declare(
    sdv_state_machine
    GIT_REPOSITORY https://github.com/yourorg/sdv-state-machine-cpp.git
    GIT_TAG v0.1.0
)
FetchContent_MakeAvailable(sdv_state_machine)

target_link_libraries(your_target PRIVATE sdv::state_machine)
```

### Building from source

```bash
mkdir build && cd build
cmake .. -DBUILD_EXAMPLES=ON -DWITH_PROMETHEUS=ON
make -j$(nproc)
sudo make install
```

## Quick Start

```cpp
#include <sdv/state_machine/state_machine.hpp>
#include <glog/logging.h>

// Define states
enum class DoorState {
    Closed,
    Opening,
    Open,
    Closing,
    Error
};

int main(int argc, char* argv[]) {
    // Initialize Google logging
    google::InitGoogleLogging(argv[0]);
    FLAGS_logtostderr = 1;
    
    // Create state machine
    sdv::StateMachine<DoorState> door_sm("DoorController", DoorState::Closed);
    
    // Define transitions
    door_sm.add_transition(
        DoorState::Closed, 
        DoorState::Opening, 
        "open_requested"
    );
    
    door_sm.add_transition(
        DoorState::Opening,
        DoorState::Open,
        "door_opened"
    );
    
    // Define state with actions
    door_sm.define_state(DoorState::Opening)
        .on_entry([]() { 
            LOG(INFO) << "Starting door motor"; 
        })
        .on_exit([]() { 
            LOG(INFO) << "Stopping door motor"; 
        });
    
    // Trigger transition
    if (door_sm.trigger("open_requested")) {
        LOG(INFO) << "Door is now: " << door_sm.current_state_name();
    }
    
    return 0;
}
```

## Advanced Usage

### Structured Logging Output

```cpp
// All state changes are logged with structured format:
// [SM:DoorController] TRANSITION: CLOSED -> OPENING | trigger=open_requested
// [SM:DoorController] STATE: current=OPENING
// [SM:DoorController] BLOCKED: trigger='invalid' from=OPENING to=CLOSED reason=no_transition

// Enable verbose logging for more details:
// GLOG_v=1 ./your_app
// [SM:DoorController] Processing trigger='open_requested' state=CLOSED
// [SM:DoorController] Entering state=OPENING
// [SM:DoorController] Exiting state=CLOSED duration=5.234s
```

### Hierarchical States

```cpp
#include <sdv/state_machine/hierarchical_state_machine.hpp>

enum class VehicleState {
    Parked,
    Driving,
    Charging
};

enum class DrivingSubstate {
    Manual,
    CruiseControl,
    Autonomous  
};

sdv::HierarchicalStateMachine<VehicleState> vehicle_sm(
    "VehicleController",
    VehicleState::Parked
);

// Define composite state
vehicle_sm.add_composite_state(
    VehicleState::Driving,
    {DrivingSubstate::Manual, DrivingSubstate::CruiseControl, DrivingSubstate::Autonomous},
    DrivingSubstate::Manual  // Initial substate
);
```

### Async Transitions

```cpp
// Async condition
door_sm.add_transition(
    DoorState::Closed,
    DoorState::Opening,
    "open_requested",
    [](const auto& context) -> std::future<bool> {
        return std::async(std::launch::async, []() {
            // Check if door is unlocked
            return check_door_unlocked();
        });
    }
);

// Async action
door_sm.add_transition(
    DoorState::Opening,
    DoorState::Open,
    "door_opened",
    {},  // no condition
    [](const auto& context) -> std::future<void> {
        return std::async(std::launch::async, []() {
            // Log door opening
            log_door_event("opened");
        });
    }
);
```

### Thread-Safe Operations

```cpp
// State machine is thread-safe by default
std::thread t1([&door_sm]() {
    door_sm.trigger("open_requested");
});

std::thread t2([&door_sm]() {
    auto state = door_sm.current_state();
    auto history = door_sm.get_history();
});

t1.join();
t2.join();
```

## Prometheus Metrics

When built with Prometheus support, the following metrics are automatically exposed:

```cpp
// Access metrics registry
auto& registry = door_sm.metrics_registry();

// Metrics exposed:
// - doorcontroller_state (current state as enum)
// - doorcontroller_state_duration_seconds (histogram)
// - doorcontroller_transitions_total (counter)
// - doorcontroller_transition_latency_seconds (histogram)
```

Example Prometheus queries:
```promql
# Current state
doorcontroller_state

# Transition rate
rate(doorcontroller_transitions_total[5m])

# P99 transition latency
histogram_quantile(0.99, doorcontroller_transition_latency_seconds)
```


## API Reference

### StateMachine<StateT>

```cpp
template<typename StateT>
class StateMachine {
public:
    // Construction
    StateMachine(std::string name, StateT initial_state);
    
    // Transitions
    void add_transition(StateT from, StateT to, std::string trigger,
                       ConditionFunc condition = {},
                       ActionFunc action = {});
    
    // State configuration
    StateBuilder<StateT> define_state(StateT state);
    
    // Trigger events
    bool trigger(std::string event, Context context = {});
    std::future<bool> trigger_async(std::string event, Context context = {});
    
    // Query
    StateT current_state() const;
    std::string current_state_name() const;
    std::vector<std::string> available_triggers() const;
};
```

## Building Examples

```bash
cd build
cmake .. -DBUILD_EXAMPLES=ON
make examples

# Run door example
./examples/door_example

# Run vehicle example  
./examples/vehicle_example
```

## Testing

```bash
cd build
cmake .. -DBUILD_TESTS=ON
make test
```

## License

Apache License 2.0