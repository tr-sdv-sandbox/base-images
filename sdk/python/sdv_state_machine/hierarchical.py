"""
Hierarchical state machine implementation with composite states support.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Set, Type
from .core import StateMachine, StateType

logger = logging.getLogger(__name__)


class HierarchicalStateMachine(StateMachine):
    """
    Extended state machine with hierarchical (composite) state support.
    
    Supports:
    - Nested states
    - State inheritance
    - Automatic parent state entry/exit
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._active_states: Set[StateType] = set()
        self._parent_child_map: Dict[StateType, Set[StateType]] = {}
        self._child_parent_map: Dict[StateType, StateType] = {}
        self._initial_child_map: Dict[StateType, StateType] = {}
        
    def add_composite_state(self,
                           parent: StateType,
                           children: List[StateType],
                           initial_child: StateType):
        """
        Define a composite state with substates.
        
        Args:
            parent: The parent composite state
            children: List of child states
            initial_child: Which child state to enter by default
        """
        if initial_child not in children:
            raise ValueError(f"{initial_child} not in children list")
            
        self._parent_child_map[parent] = set(children)
        self._initial_child_map[parent] = initial_child
        
        # Build reverse mapping
        for child in children:
            self._child_parent_map[child] = parent
            
        logger.debug(f"Added composite state {parent.name} with children: {[c.name for c in children]}")
        
    def is_in_state(self, state: StateType) -> bool:
        """
        Check if state machine is in a particular state.
        
        This includes parent states - if we're in a child state,
        we're also considered to be in its parent state.
        """
        if state == self.current_state:
            return True
            
        # Check if current state is a child of the queried state
        if state in self._parent_child_map:
            return self.current_state in self._parent_child_map[state]
            
        return False
        
    def get_active_states(self) -> Set[StateType]:
        """Get all currently active states (including parents)"""
        return self._active_states.copy()
        
    async def _enter_state(self, state: StateType):
        """Enhanced enter state for hierarchical states"""
        # Check if this is a child state
        parent = self._child_parent_map.get(state)
        
        if parent and parent not in self._active_states:
            # Need to enter parent first (without its default child)
            await self._enter_state_internal(parent, enter_default_child=False)
            
        # Enter the target state
        await self._enter_state_internal(state, enter_default_child=True)
        
    async def _enter_state_internal(self, state: StateType, enter_default_child: bool = True):
        """Internal state entry logic"""
        # Add to active states
        self._active_states.add(state)
        
        # Call parent implementation
        await super()._enter_state(state)
        
        # If this is a parent state and we should enter default child
        if enter_default_child and state in self._initial_child_map:
            default_child = self._initial_child_map[state]
            await self._enter_state_internal(default_child)
            
        # Update VSS with full state hierarchy
        if (self.dev_mode or self.test_mode) and self.kuksa_client:
            await self._update_hierarchical_vss_state()
            
    async def _exit_state(self, state: StateType):
        """Enhanced exit state for hierarchical states"""
        # If exiting a parent state, exit all its children first
        if state in self._parent_child_map:
            for child in self._parent_child_map[state]:
                if child in self._active_states:
                    await self._exit_state(child)
                    
        # Remove from active states
        self._active_states.discard(state)
        
        # Call parent implementation
        await super()._exit_state(state)
        
    async def _update_hierarchical_vss_state(self):
        """Update VSS with hierarchical state information"""
        if not self.kuksa_client:
            return
            
        try:
            # Build state path (e.g., "ACTIVE.CRUISING")
            state_path = self._get_state_path(self.current_state)
            
            await self.kuksa_client.set(
                f"{self._vss_namespace}.CurrentStatePath",
                state_path
            )
            
            # List all active states
            active_state_names = [s.name for s in sorted(
                self._active_states,
                key=lambda x: x.name
            )]
            
            await self.kuksa_client.set(
                f"{self._vss_namespace}.ActiveStates",
                ",".join(active_state_names)
            )
            
            # Determine depth level
            depth = len(state_path.split('.'))
            await self.kuksa_client.set(
                f"{self._vss_namespace}.StateDepth",
                depth
            )
            
        except Exception as e:
            logger.warning(f"Failed to update hierarchical VSS state: {e}")
            
    def _get_state_path(self, state: StateType) -> str:
        """Get full hierarchical path of a state"""
        path_parts = [state.name]
        current = state
        
        while current in self._child_parent_map:
            parent = self._child_parent_map[current]
            path_parts.insert(0, parent.name)
            current = parent
            
        return ".".join(path_parts)
        
    def get_state_depth(self, state: Optional[StateType] = None) -> int:
        """Get the hierarchical depth of a state"""
        if state is None:
            state = self.current_state
            
        depth = 0
        current = state
        
        while current in self._child_parent_map:
            depth += 1
            current = self._child_parent_map[current]
            
        return depth
        
    def get_leaf_state(self) -> StateType:
        """Get the deepest active state (leaf state)"""
        # Find state with no active children
        for state in self._active_states:
            has_active_child = False
            if state in self._parent_child_map:
                for child in self._parent_child_map[state]:
                    if child in self._active_states:
                        has_active_child = True
                        break
                        
            if not has_active_child:
                return state
                
        return self.current_state
        
    def visualize(self) -> str:
        """Generate hierarchical state diagram in PlantUML format"""
        lines = ["@startuml", f"title {self.name} Hierarchical State Machine", ""]
        
        # Define composite states
        for parent, children in self._parent_child_map.items():
            lines.append(f"state {parent.name} {{")
            
            for child in children:
                if child == self.current_state:
                    lines.append(f"  state {child.name} #yellow : Current State")
                elif child in self._active_states:
                    lines.append(f"  state {child.name} #lightblue : Active")
                else:
                    lines.append(f"  state {child.name}")
                    
            # Mark initial child
            initial = self._initial_child_map.get(parent)
            if initial:
                lines.append(f"  [*] --> {initial.name}")
                
            lines.append("}")
            lines.append("")
            
        # Add simple states
        for state in self.states:
            if state not in self._parent_child_map and state not in self._child_parent_map:
                if state == self.current_state:
                    lines.append(f"state {state.name} #yellow : Current State")
                elif state in self._active_states:
                    lines.append(f"state {state.name} #lightblue : Active")
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