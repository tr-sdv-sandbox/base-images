"""
SDV State Machine Library

A state machine implementation with dual observability for SDV applications.
"""

__version__ = "0.1.0"

from .core import (
    StateType,
    StateMachine,
    Transition,
    StateDefinition,
)

from .hierarchical import HierarchicalStateMachine
from .distributed import DistributedStateMachine
from .factory import StateMachineFactory

__all__ = [
    "StateType",
    "StateMachine",
    "HierarchicalStateMachine",
    "DistributedStateMachine",
    "Transition",
    "StateDefinition",
    "StateMachineFactory",
]