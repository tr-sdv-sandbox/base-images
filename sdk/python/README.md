# SDV State Machine SDK (Python)

A state machine library designed for Software-Defined Vehicle applications with dual observability:
- Development/test introspection via VSS signals
- Production monitoring via Prometheus metrics

## Features

- **Type-safe state definitions** using Python Enums
- **Hierarchical states** with composite state support
- **Async-first design** for modern Python applications
- **Development mode** with VSS introspection
- **Production metrics** via Prometheus
- **State persistence** and recovery
- **Distributed coordination** support
- **Comprehensive testing utilities**

## Installation

```bash
# Basic installation
pip install sdv-state-machine

# With KUKSA support
pip install sdv-state-machine[kuksa]

# With Redis support for distributed systems
pip install sdv-state-machine[kuksa,redis]

# Development installation
pip install -e .[dev]
```

## Quick Start

```python
from enum import auto
from sdv_state_machine import StateMachine, StateType

# Define states
class DoorState(StateType):
    CLOSED = auto()
    OPENING = auto()
    OPEN = auto()
    CLOSING = auto()
    ERROR = auto()

# Create state machine
door_sm = StateMachine(
    name="DoorController",
    states=DoorState,
    initial_state=DoorState.CLOSED
)

# Define transitions
door_sm.add_transition(
    from_state=DoorState.CLOSED,
    to_state=DoorState.OPENING,
    trigger="open_requested"
)

# Use in application
async def handle_door_open():
    success = await door_sm.trigger("open_requested")
    if success:
        print(f"Door is now {door_sm.current_state.name}")
```

## Advanced Usage

### With KUKSA Integration (Development Mode)

```python
from kuksa_client import KuksaClient
from sdv_state_machine import StateMachine

# Enable development mode introspection
kuksa_client = KuksaClient("grpc://localhost:55555")

door_sm = StateMachine(
    name="DoorController",
    states=DoorState,
    initial_state=DoorState.CLOSED,
    kuksa_client=kuksa_client  # Enables VSS introspection
)

# State changes are now visible at:
# Private.StateMachine.DoorController.CurrentState
# Private.StateMachine.DoorController.History
```

### Hierarchical States

```python
from sdv_state_machine import HierarchicalStateMachine

# Main states
class VehicleState(StateType):
    PARKED = auto()
    DRIVING = auto()
    CHARGING = auto()

# Driving substates
class DrivingSubstate(StateType):
    MANUAL = auto()
    CRUISE_CONTROL = auto()
    AUTONOMOUS = auto()

vehicle_sm = HierarchicalStateMachine(
    name="VehicleController",
    states=VehicleState,
    initial_state=VehicleState.PARKED
)

# Define composite state
vehicle_sm.add_composite_state(
    parent=VehicleState.DRIVING,
    children=[DrivingSubstate.MANUAL, DrivingSubstate.CRUISE_CONTROL, DrivingSubstate.AUTONOMOUS],
    initial_child=DrivingSubstate.MANUAL
)
```

### State Actions

```python
# Define state with entry/exit actions
door_sm.define_state(
    state=DoorState.OPENING,
    entry_action=start_door_motor,
    exit_action=stop_door_motor
)

async def start_door_motor():
    await set_motor_speed(100)
    logger.info("Door motor started")

async def stop_door_motor():
    await set_motor_speed(0)
    logger.info("Door motor stopped")
```

## Prometheus Metrics

The library automatically exposes the following metrics:

- `{name}_state` - Current state as enum
- `{name}_state_duration_seconds` - Time spent in each state
- `{name}_transitions_total` - Count of state transitions
- `{name}_transition_latency_seconds` - Transition execution time

Example queries:
```promql
# Current state
doorcontroller_state

# Transition rate
rate(doorcontroller_transitions_total[5m])

# Average time in OPENING state
rate(doorcontroller_state_duration_seconds_sum{state="OPENING"}[5m]) /
rate(doorcontroller_state_duration_seconds_count{state="OPENING"}[5m])
```

## Testing

```python
from sdv_state_machine.testing import StateMachineTestHarness

# Create test harness
harness = StateMachineTestHarness(door_sm)

# Test state transitions
async def test_door_operation():
    await harness.assert_state(DoorState.CLOSED)
    
    await harness.trigger_and_assert(
        "open_requested", 
        DoorState.OPENING
    )
    
    # Test sequence
    await harness.assert_transition_sequence([
        ("door_opened", DoorState.OPEN),
        ("close_requested", DoorState.CLOSING),
        ("door_closed", DoorState.CLOSED)
    ])
    
    # Get coverage report
    coverage = harness.get_coverage_report()
    assert coverage['state_coverage'] == 1.0  # All states visited
```

## CLI Tool

```bash
# Monitor live state
sm-tool monitor DoorController --vss-address localhost:55555

# Visualize state machine
sm-tool visualize door_config.yaml -o door_states.png

# Trigger event remotely
sm-tool trigger DoorController open_requested --params position=full
```

## Configuration

State machines can be configured via YAML:

```yaml
# door_config.yaml
name: DoorController
states:
  - CLOSED
  - OPENING
  - OPEN
  - CLOSING
  - ERROR
initial: CLOSED
transitions:
  - from: CLOSED
    to: OPENING
    trigger: open_requested
    condition: door_not_locked
  - from: OPENING
    to: OPEN
    trigger: door_opened
  - from: OPEN
    to: CLOSING
    trigger: close_requested
```

Load from YAML:
```python
from sdv_state_machine import StateMachineFactory

door_sm = StateMachineFactory.from_yaml("door_config.yaml")
```

## License

Apache License 2.0