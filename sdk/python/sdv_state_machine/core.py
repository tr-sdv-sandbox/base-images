"""
Core state machine implementation with Prometheus metrics and optional VSS introspection.
"""

import asyncio
import logging
import os
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Type, Set
from dataclasses import dataclass, field
from prometheus_client import Counter, Histogram, Info, Enum as PrometheusEnum

logger = logging.getLogger(__name__)


class StateType(Enum):
    """Base class for state enums"""
    pass


@dataclass
class Transition:
    """Represents a state transition"""
    from_state: StateType
    to_state: StateType
    trigger: str
    condition: Optional[Callable[..., bool]] = None
    action: Optional[Callable[..., None]] = None


@dataclass
class StateDefinition:
    """Defines a state with optional actions"""
    name: str
    entry_action: Optional[Callable[[], None]] = None
    exit_action: Optional[Callable[[], None]] = None
    internal_transitions: Dict[str, Callable] = field(default_factory=dict)


class StateMachine:
    """
    A state machine with built-in observability.
    
    Features:
    - Type-safe state definitions using Enums
    - Async-first design
    - Development mode: VSS-based state introspection
    - Production mode: Prometheus metrics
    """
    
    def __init__(self,
                 name: str,
                 states: Type[StateType],
                 initial_state: StateType,
                 kuksa_client=None):
        """
        Initialize state machine.
        
        Args:
            name: Name of the state machine
            states: Enum class defining all states
            initial_state: Initial state
            kuksa_client: Optional KUKSA client for VSS introspection
        """
        self.name = name
        self.states = states
        self.current_state = initial_state
        self._transitions: Dict[str, List[Transition]] = {}
        self._state_definitions: Dict[StateType, StateDefinition] = {}
        
        # Development/test mode detection
        self.dev_mode = os.getenv('SDV_DEV_MODE', 'false').lower() == 'true'
        self.test_mode = os.getenv('SDV_TEST_MODE', 'false').lower() == 'true'
        
        # VSS client for development introspection
        self.kuksa_client = kuksa_client
        self._vss_namespace = f"Private.StateMachine.{name}"
        
        # State history for development
        self._history: List[Dict[str, Any]] = []
        self._state_entry_time = datetime.utcnow()
        
        # Initialize metrics
        self._init_metrics()
        
        # Initialize VSS signals if in dev mode
        if (self.dev_mode or self.test_mode) and self.kuksa_client:
            asyncio.create_task(self._init_vss_signals())
        
        # Enter initial state
        asyncio.create_task(self._enter_state(initial_state))
        
    def _init_metrics(self):
        """Initialize Prometheus metrics"""
        metric_name = self.name.lower().replace('-', '_')
        
        # Current state as enum metric
        state_names = [s.name.lower() for s in self.states]
        self.state_metric = PrometheusEnum(
            f'{metric_name}_state',
            f'Current state of {self.name}',
            states=state_names
        )
        
        # State duration histogram
        self.state_duration = Histogram(
            f'{metric_name}_state_duration_seconds',
            f'Time spent in each state',
            labelnames=['state'],
            buckets=(0.1, 0.5, 1, 5, 10, 30, 60, 120, 300, 600)
        )
        
        # Transition counter
        self.transition_counter = Counter(
            f'{metric_name}_transitions_total',
            f'Total state transitions',
            labelnames=['from_state', 'to_state', 'trigger']
        )
        
        # Transition latency
        self.transition_latency = Histogram(
            f'{metric_name}_transition_latency_seconds',
            f'Latency of state transitions',
            labelnames=['from_state', 'to_state'],
            buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1)
        )
        
        # State info for additional context
        self.state_info = Info(
            f'{metric_name}_state_info',
            f'Detailed state information'
        )
        
    async def _init_vss_signals(self):
        """Initialize VSS signals for development introspection"""
        if not self.kuksa_client:
            return
            
        try:
            # Register signals in private namespace
            signals = [
                f"{self._vss_namespace}.CurrentState",
                f"{self._vss_namespace}.CurrentStateValue",
                f"{self._vss_namespace}.AvailableTriggers",
                f"{self._vss_namespace}.History",
                f"{self._vss_namespace}.LastTransition.From",
                f"{self._vss_namespace}.LastTransition.To",
                f"{self._vss_namespace}.LastTransition.Trigger",
                f"{self._vss_namespace}.LastTransition.Timestamp",
            ]
            
            # In a real implementation, you would register these with the databroker
            logger.info(f"Initialized VSS signals for {self.name}: {signals}")
            
        except Exception as e:
            logger.warning(f"Failed to initialize VSS signals: {e}")
            
    def add_transition(self,
                      from_state: StateType,
                      to_state: StateType,
                      trigger: str,
                      condition: Optional[Callable[..., bool]] = None,
                      action: Optional[Callable[..., None]] = None):
        """Add a transition between states"""
        key = f"{from_state.value}:{trigger}"
        if key not in self._transitions:
            self._transitions[key] = []
            
        self._transitions[key].append(Transition(
            from_state=from_state,
            to_state=to_state,
            trigger=trigger,
            condition=condition,
            action=action
        ))
        
        logger.debug(f"Added transition: {from_state.name} -> {to_state.name} on {trigger}")
        
    def define_state(self,
                    state: StateType,
                    entry_action: Optional[Callable[[], None]] = None,
                    exit_action: Optional[Callable[[], None]] = None):
        """Define state with optional entry/exit actions"""
        self._state_definitions[state] = StateDefinition(
            name=state.name,
            entry_action=entry_action,
            exit_action=exit_action
        )
        
    async def trigger(self, event: str, **kwargs) -> bool:
        """
        Trigger a state transition.
        
        Returns:
            True if transition occurred, False otherwise.
        """
        transition_start = datetime.utcnow()
        key = f"{self.current_state.value}:{event}"
        
        logger.debug(f"Attempting trigger: {event} from state {self.current_state.name}")
        
        if key not in self._transitions:
            logger.debug(f"No transition for {key}")
            return False
            
        # Find valid transition
        for transition in self._transitions[key]:
            # Check condition
            if transition.condition:
                try:
                    if asyncio.iscoroutinefunction(transition.condition):
                        condition_met = await transition.condition(**kwargs)
                    else:
                        condition_met = transition.condition(**kwargs)
                        
                    if not condition_met:
                        logger.debug(f"Condition not met for transition to {transition.to_state.name}")
                        continue
                except Exception as e:
                    logger.error(f"Condition check failed: {e}")
                    continue
                    
            # Valid transition found
            old_state = self.current_state
            
            try:
                # Exit current state
                await self._exit_state(old_state)
                
                # Execute transition action
                if transition.action:
                    if asyncio.iscoroutinefunction(transition.action):
                        await transition.action(**kwargs)
                    else:
                        transition.action(**kwargs)
                        
                # Enter new state
                await self._enter_state(transition.to_state)
                
                # Record transition
                await self._record_transition(
                    old_state,
                    transition.to_state,
                    event,
                    transition_start,
                    kwargs
                )
                
                logger.info(f"Transitioned: {old_state.name} -> {transition.to_state.name} via {event}")
                return True
                
            except Exception as e:
                logger.error(f"Transition failed: {e}")
                # Try to recover by entering error state if defined
                if hasattr(self.states, 'ERROR'):
                    await self._enter_state(self.states.ERROR)
                raise
                
        return False
        
    async def _enter_state(self, state: StateType):
        """Enter a state"""
        self.current_state = state
        self._state_entry_time = datetime.utcnow()
        
        # Execute entry action
        if state in self._state_definitions:
            entry_action = self._state_definitions[state].entry_action
            if entry_action:
                if asyncio.iscoroutinefunction(entry_action):
                    await entry_action()
                else:
                    entry_action()
                    
        # Update Prometheus
        self.state_metric.state(state.name.lower())
        
        # Update VSS in dev mode
        if (self.dev_mode or self.test_mode) and self.kuksa_client:
            await self._update_vss_state(state)
            
    async def _exit_state(self, state: StateType):
        """Exit a state"""
        # Record time spent in state
        duration = (datetime.utcnow() - self._state_entry_time).total_seconds()
        self.state_duration.labels(state=state.name).observe(duration)
        
        # Execute exit action
        if state in self._state_definitions:
            exit_action = self._state_definitions[state].exit_action
            if exit_action:
                if asyncio.iscoroutinefunction(exit_action):
                    await exit_action()
                else:
                    exit_action()
                    
    async def _record_transition(self,
                               from_state: StateType,
                               to_state: StateType,
                               trigger: str,
                               start_time: datetime,
                               context: Dict[str, Any]):
        """Record transition in metrics and history"""
        # Calculate latency
        latency = (datetime.utcnow() - start_time).total_seconds()
        
        # Prometheus metrics
        self.transition_counter.labels(
            from_state=from_state.name,
            to_state=to_state.name,
            trigger=trigger
        ).inc()
        
        self.transition_latency.labels(
            from_state=from_state.name,
            to_state=to_state.name
        ).observe(latency)
        
        # Update state info
        self.state_info.info({
            'state': to_state.name,
            'previous_state': from_state.name,
            'trigger': trigger,
            'timestamp': str(int(datetime.utcnow().timestamp()))
        })
        
        # Add to history
        transition_record = {
            'timestamp': datetime.utcnow().isoformat(),
            'from': from_state.name,
            'to': to_state.name,
            'trigger': trigger,
            'latency_ms': latency * 1000,
            'context': context
        }
        
        self._history.append(transition_record)
        if len(self._history) > 20:  # Keep last 20 transitions
            self._history.pop(0)
            
    async def _update_vss_state(self, state: StateType):
        """Update VSS signals in development mode"""
        if not self.kuksa_client:
            return
            
        try:
            # Current state
            await self.kuksa_client.set(
                f"{self._vss_namespace}.CurrentState",
                state.name
            )
            
            # State value (for numeric comparisons)
            await self.kuksa_client.set(
                f"{self._vss_namespace}.CurrentStateValue",
                state.value if isinstance(state.value, (int, float)) else hash(state.value)
            )
            
            # Available triggers
            triggers = self.get_available_triggers()
            await self.kuksa_client.set(
                f"{self._vss_namespace}.AvailableTriggers",
                ",".join(triggers)
            )
            
            # Last transition
            if self._history:
                last = self._history[-1]
                await self.kuksa_client.set(
                    f"{self._vss_namespace}.LastTransition.From",
                    last['from']
                )
                await self.kuksa_client.set(
                    f"{self._vss_namespace}.LastTransition.To",
                    last['to']
                )
                await self.kuksa_client.set(
                    f"{self._vss_namespace}.LastTransition.Trigger",
                    last['trigger']
                )
                
        except Exception as e:
            logger.warning(f"Failed to update VSS state: {e}")
            
    # Public API for introspection
    def get_state(self) -> StateType:
        """Get current state"""
        return self.current_state
        
    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get state transition history"""
        return self._history[-limit:]
        
    def get_available_triggers(self) -> List[str]:
        """Get available triggers from current state"""
        triggers = []
        prefix = f"{self.current_state.value}:"
        
        for key in self._transitions:
            if key.startswith(prefix):
                trigger = key[len(prefix):]
                triggers.append(trigger)
                
        return sorted(set(triggers))
        
    def visualize(self) -> str:
        """Generate state diagram in PlantUML format"""
        lines = ["@startuml", f"title {self.name} State Machine", ""]
        
        # Add states
        for state in self.states:
            if state == self.current_state:
                lines.append(f"state {state.name} #yellow : Current State")
            else:
                lines.append(f"state {state.name}")
                
        lines.append("")
        
        # Add transitions
        processed = set()
        for transitions in self._transitions.values():
            for trans in transitions:
                key = f"{trans.from_state.name}->{trans.to_state.name}"
                if key not in processed:
                    label = trans.trigger
                    if trans.condition:
                        label += " [guarded]"
                    lines.append(f"{trans.from_state.name} --> {trans.to_state.name} : {label}")
                    processed.add(key)
                    
        lines.append("@enduml")
        return "\n".join(lines)