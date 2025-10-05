"""
State machine tracking by parsing structured logs from C++ SDK.
Tracks current state and transitions for all state machines.
"""

import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from enum import Enum


class TransitionType(Enum):
    """Types of state machine events from logs"""
    INIT = "INIT"
    TRANSITION = "TRANSITION" 
    STATE = "STATE"
    BLOCKED = "BLOCKED"
    IGNORED = "IGNORED"


@dataclass
class TransitionEvent:
    """Parsed state transition event"""
    timestamp: datetime
    state_machine: str
    event_type: TransitionType
    from_state: Optional[str] = None
    to_state: Optional[str] = None
    current_state: Optional[str] = None
    trigger: Optional[str] = None
    reason: Optional[str] = None
    raw_log: str = ""


class StateTracker:
    """
    Tracks state machine states by parsing logs.
    
    Expected log formats:
    - [SM:Name] INIT: state=StateName
    - [SM:Name] TRANSITION: StateA -> StateB | trigger=event
    - [SM:Name] STATE: current=StateName  
    - [SM:Name] BLOCKED: trigger='event' from=StateA to=StateB reason=condition_failed
    - [SM:Name] IGNORED: trigger='event' state=StateA reason=no_transition
    """
    
    # Regex patterns for parsing logs
    PATTERNS = {
        'init': re.compile(r'\[SM:(\w+)\] INIT: state=(\w+)'),
        'transition': re.compile(r'\[SM:(\w+)\] TRANSITION: (\w+) -> (\w+) \| trigger=(\w+)'),
        'state': re.compile(r'\[SM:(\w+)\] STATE: current=(\w+)'),
        'blocked': re.compile(r'\[SM:(\w+)\] BLOCKED: trigger=\'(\w+)\' from=(\w+) to=(\w+) reason=(\w+)'),
        'ignored': re.compile(r'\[SM:(\w+)\] IGNORED: trigger=\'(\w+)\' state=(\w+) reason=(\w+)')
    }
    
    def __init__(self):
        self._lock = threading.Lock()
        self._current_states: Dict[str, str] = {}  # machine_name -> current_state
        self._transitions: List[TransitionEvent] = []
        self._blocked_events: List[TransitionEvent] = []
        
    def process_log_line(self, line: str, timestamp: Optional[datetime] = None) -> Optional[TransitionEvent]:
        """
        Process a single log line and extract state information.
        Returns the parsed event if it's a state machine log, None otherwise.
        """
        if timestamp is None:
            timestamp = datetime.now()
            
        # Try to parse timestamp from log if present
        timestamp_match = re.match(r'^([IEW])(\d{8}) (\d{2}:\d{2}:\d{2}\.\d+) \d+ \S+\] (.*)$', line)
        if timestamp_match:
            # Extract actual log content after glog prefix
            line = timestamp_match.group(4)
        
        # Check each pattern
        for pattern_type, pattern in self.PATTERNS.items():
            match = pattern.search(line)
            if match:
                event = self._parse_event(pattern_type, match, timestamp, line)
                if event:
                    self._update_state(event)
                return event
                
        return None
    
    def _parse_event(self, pattern_type: str, match: re.Match, 
                     timestamp: datetime, raw_log: str) -> Optional[TransitionEvent]:
        """Parse matched pattern into TransitionEvent"""
        
        if pattern_type == 'init':
            sm_name, state = match.groups()
            return TransitionEvent(
                timestamp=timestamp,
                state_machine=sm_name,
                event_type=TransitionType.INIT,
                current_state=state,
                raw_log=raw_log
            )
            
        elif pattern_type == 'transition':
            sm_name, from_state, to_state, trigger = match.groups()
            return TransitionEvent(
                timestamp=timestamp,
                state_machine=sm_name,
                event_type=TransitionType.TRANSITION,
                from_state=from_state,
                to_state=to_state,
                trigger=trigger,
                raw_log=raw_log
            )
            
        elif pattern_type == 'state':
            sm_name, state = match.groups()
            return TransitionEvent(
                timestamp=timestamp,
                state_machine=sm_name,
                event_type=TransitionType.STATE,
                current_state=state,
                raw_log=raw_log
            )
            
        elif pattern_type == 'blocked':
            sm_name, trigger, from_state, to_state, reason = match.groups()
            return TransitionEvent(
                timestamp=timestamp,
                state_machine=sm_name,
                event_type=TransitionType.BLOCKED,
                from_state=from_state,
                to_state=to_state,
                trigger=trigger,
                reason=reason,
                raw_log=raw_log
            )
            
        elif pattern_type == 'ignored':
            sm_name, trigger, state, reason = match.groups()
            return TransitionEvent(
                timestamp=timestamp,
                state_machine=sm_name,
                event_type=TransitionType.IGNORED,
                current_state=state,
                trigger=trigger,
                reason=reason,
                raw_log=raw_log
            )
            
        return None
    
    def _update_state(self, event: TransitionEvent):
        """Update internal state based on event"""
        with self._lock:
            if event.event_type == TransitionType.INIT:
                self._current_states[event.state_machine] = event.current_state
                
            elif event.event_type == TransitionType.TRANSITION:
                self._current_states[event.state_machine] = event.to_state
                self._transitions.append(event)
                
            elif event.event_type == TransitionType.STATE:
                self._current_states[event.state_machine] = event.current_state
                
            elif event.event_type == TransitionType.BLOCKED:
                self._blocked_events.append(event)
                
            # IGNORED events don't change state
    
    def get_current_state(self, state_machine: str) -> Optional[str]:
        """Get current state of a state machine"""
        with self._lock:
            return self._current_states.get(state_machine)
    
    def get_all_states(self) -> Dict[str, str]:
        """Get current states of all tracked state machines"""
        with self._lock:
            return self._current_states.copy()
    
    def get_transitions(self, state_machine: Optional[str] = None) -> List[TransitionEvent]:
        """Get transition history, optionally filtered by state machine"""
        with self._lock:
            if state_machine:
                return [t for t in self._transitions if t.state_machine == state_machine]
            return self._transitions.copy()
    
    def get_blocked_events(self, state_machine: Optional[str] = None) -> List[TransitionEvent]:
        """Get blocked transition attempts"""
        with self._lock:
            if state_machine:
                return [e for e in self._blocked_events if e.state_machine == state_machine]
            return self._blocked_events.copy()
    
    def wait_for_state(self, state_machine: str, expected_state: str,
                      timeout: float = 5.0) -> bool:
        """
        Wait for a state machine to reach a specific state.
        Returns True if state is reached within timeout.
        """
        import time
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self.get_current_state(state_machine) == expected_state:
                return True
            time.sleep(0.1)

        return False

    def wait_for_transition(self, state_machine: str, from_state: str, to_state: str,
                           trigger: Optional[str] = None, timeout: float = 5.0) -> bool:
        """
        Wait for a specific transition to occur.
        Returns True if transition is found (including past transitions) within timeout.
        """
        import time
        start_time = time.time()

        while time.time() - start_time < timeout:
            transitions = self.get_transitions(state_machine)
            # Check all transitions (including ones that already occurred)
            for t in transitions:
                if t.from_state == from_state and t.to_state == to_state:
                    if trigger is None or t.trigger == trigger:
                        return True
            time.sleep(0.1)

        return False

    def verify_transition_sequence(self, state_machine: str, 
                                 expected_sequence: List[Tuple[str, str]]) -> bool:
        """
        Verify that a state machine went through expected transition sequence.
        expected_sequence: List of (from_state, to_state) tuples
        """
        transitions = self.get_transitions(state_machine)
        
        if len(transitions) < len(expected_sequence):
            return False
            
        # Check last N transitions match expected sequence
        actual_sequence = [(t.from_state, t.to_state) for t in transitions[-len(expected_sequence):]]
        return actual_sequence == expected_sequence
    
    def clear(self):
        """Clear all tracked state"""
        with self._lock:
            self._current_states.clear()
            self._transitions.clear()
            self._blocked_events.clear()
    
    def get_state_machines(self) -> List[str]:
        """Get list of all tracked state machines"""
        with self._lock:
            return list(self._current_states.keys())


class LogStreamProcessor:
    """
    Process log streams in real-time and track state changes.
    Can be used with subprocess output or log file tailing.
    """
    
    def __init__(self, state_tracker: StateTracker):
        self.state_tracker = state_tracker
        self._stop = threading.Event()
        self._thread = None
        
    def process_stream(self, stream):
        """Process a stream of log lines"""
        for line in stream:
            if self._stop.is_set():
                break
            if isinstance(line, bytes):
                line = line.decode('utf-8')
            line = line.strip()
            if line:
                self.state_tracker.process_log_line(line)
    
    def start_async(self, stream):
        """Start processing stream in background thread"""
        self._thread = threading.Thread(target=self.process_stream, args=(stream,))
        self._thread.daemon = True
        self._thread.start()
        
    def stop(self):
        """Stop async processing"""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)