"""
KUKSA Test Framework v4

A comprehensive test framework combining practical features with formal specifications.
"""

from .models import (
    Signal, Requirement, StateMachine, StateTransition,
    VFFSpec, TestCase, TestStep, TestResult
)
from .parser import SpecParser, TestParser
from .runner import TestRunner
from .client import KuksaClient
from .state_tracker import StateTracker
from .reporter import TestReporter

__version__ = "4.0.0"
__all__ = [
    "Signal", "Requirement", "StateMachine", "StateTransition",
    "VFFSpec", "TestCase", "TestStep", "TestResult",
    "SpecParser", "TestParser", "TestRunner", 
    "KuksaClient", "StateTracker", "TestReporter"
]