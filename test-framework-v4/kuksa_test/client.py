"""
Enhanced KUKSA client with actuator mode support and signal validation.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass

from kuksa_client.grpc import VSSClient
from kuksa_client.grpc import Datapoint

from .models import Signal, SignalType, ActuatorMode


logger = logging.getLogger(__name__)


@dataclass
class SignalValue:
    """Enhanced signal value with metadata"""
    path: str
    value: Any
    mode: Optional[ActuatorMode] = None  # For actuators
    timestamp: Optional[float] = None
    datapoint: Optional[Datapoint] = None  # Raw KUKSA datapoint


class KuksaClient:
    """
    Enhanced KUKSA client with VFF signal support.
    
    Features:
    - Actuator mode support (target vs actual)
    - Signal validation against VFF spec
    - Batch operations
    - Async support
    """
    
    def __init__(self, url: str = "127.0.0.1:55556", token: Optional[str] = None):
        self.url = url
        self.token = token
        self._client: Optional[VSSClient] = None
        self._connected = False
        
    async def connect(self):
        """Connect to KUKSA databroker"""
        if self._connected:
            return
            
        try:
            # Parse host and port from URL
            if ':' in self.url:
                host, port = self.url.split(':', 1)
                port = int(port)
            else:
                host = self.url
                port = 55556
            
            self._client = VSSClient(host, port, token=self.token, ensure_startup_connection=False)
            self._client.connect()
            self._connected = True
            logger.info(f"Connected to KUKSA at {host}:{port}")
        except Exception as e:
            logger.error(f"Failed to connect to KUKSA: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from KUKSA databroker"""
        if self._client and self._connected:
            self._client.disconnect()
            self._connected = False
            logger.info("Disconnected from KUKSA")
    
    async def get_value(self, path: str, mode: Optional[ActuatorMode] = None) -> SignalValue:
        """
        Get a signal value.

        Args:
            path: VSS signal path
            mode: For actuators, specify TARGET or ACTUAL (default: ACTUAL)

        Returns:
            SignalValue with current value and metadata
        """
        if not self._connected:
            await self.connect()

        try:
            # Use appropriate method based on mode
            if mode == ActuatorMode.TARGET:
                response = self._client.get_target_values([path])
            else:
                # Default to current/actual values
                response = self._client.get_current_values([path])

            if path in response:
                dp = response[path]
                if dp is None:
                    raise ValueError(f"Signal {path} has no value set")
                return SignalValue(
                    path=path,
                    value=self._extract_value(dp),
                    mode=mode,
                    timestamp=dp.timestamp.seconds if hasattr(dp.timestamp, 'seconds') else None,
                    datapoint=dp
                )
            else:
                raise ValueError(f"Signal {path} not found")

        except Exception as e:
            logger.error(f"Failed to get value for {path}: {e}")
            raise
    
    async def set_value(self, path: str, value: Any, mode: Optional[ActuatorMode] = None):
        """
        Set a signal value.

        Args:
            path: VSS signal path
            value: Value to set
            mode: For actuators, specify TARGET or ACTUAL. For sensors/attributes, leave as None (uses current values)
        """
        if not self._connected:
            await self.connect()

        try:
            # Build datapoint
            datapoint = self._build_datapoint(value)

            # Use appropriate method based on mode
            if mode == ActuatorMode.TARGET:
                # Set target value for actuators
                self._client.set_target_values({path: datapoint})
            else:
                # Default to current values (for sensors, attributes, or actuator actual values)
                self._client.set_current_values({path: datapoint})

            logger.debug(f"Set {path} = {value} (mode: {mode or 'current'})")

        except Exception as e:
            logger.error(f"Failed to set value for {path}: {e}")
            raise
    
    async def get_values(self, paths: List[str]) -> Dict[str, SignalValue]:
        """Get multiple signal values in one call (gets current/actual values)"""
        if not self._connected:
            await self.connect()

        try:
            # Get all current values
            response = self._client.get_current_values(paths)

            # Convert to SignalValue objects
            result = {}
            for path, dp in response.items():
                result[path] = SignalValue(
                    path=path,
                    value=self._extract_value(dp),
                    mode=ActuatorMode.ACTUAL,  # Current values are actual
                    timestamp=dp.timestamp.seconds if hasattr(dp.timestamp, 'seconds') else None,
                    datapoint=dp
                )

            return result

        except Exception as e:
            logger.error(f"Failed to get values: {e}")
            raise
    
    async def set_values(self, updates: Dict[str, Any]):
        """Set multiple signal values in one call"""
        if not self._connected:
            await self.connect()

        try:
            # Separate target and current/actual updates
            target_updates = {}
            current_updates = {}

            for path, value in updates.items():
                # Handle actuator paths with mode
                if isinstance(value, dict) and 'value' in value:
                    mode = value.get('mode')
                    datapoint = self._build_datapoint(value['value'])
                    # mode can be either string 'target' or ActuatorMode.TARGET enum
                    if mode == 'target' or mode == ActuatorMode.TARGET:
                        target_updates[path] = datapoint
                    else:
                        current_updates[path] = datapoint
                else:
                    # Default to current values for simple values (sensors/attributes)
                    current_updates[path] = self._build_datapoint(value)

            # Set values using appropriate methods
            if target_updates:
                for path in target_updates.keys():
                    logger.info(f"Injecting {path} [TARGET]")
                self._client.set_target_values(target_updates)
            if current_updates:
                for path in current_updates.keys():
                    logger.info(f"Injecting {path} [VALUE]")
                self._client.set_current_values(current_updates)

            logger.debug(f"Set {len(target_updates)} target + {len(current_updates)} current values")

        except Exception as e:
            logger.error(f"Failed to set values: {e}")
            raise
    
    
    def _extract_value(self, datapoint: Datapoint) -> Any:
        """Extract value from KUKSA datapoint"""
        # Datapoint has a direct value attribute
        return datapoint.value
    
    def _build_datapoint(self, value: Any) -> Datapoint:
        """Build KUKSA datapoint from value"""
        # Datapoint constructor takes the value directly
        return Datapoint(value)
    
    def subscribe_target_values(self, paths: List[str]):
        """
        Subscribe to target value changes for actuators.

        Args:
            paths: List of VSS signal paths to subscribe to

        Yields:
            Dict[str, SignalValue] for each update
        """
        if not self._connected:
            raise RuntimeError("Not connected to KUKSA")

        # Subscribe to target values
        for updates in self._client.subscribe_target_values(paths):
            result = {}
            for path, dp in updates.items():
                if dp is not None:
                    result[path] = SignalValue(
                        path=path,
                        value=self._extract_value(dp),
                        mode=ActuatorMode.TARGET,
                        timestamp=dp.timestamp.seconds if hasattr(dp.timestamp, 'seconds') else None,
                        datapoint=dp
                    )
            if result:
                yield result

    def subscribe_current_values(self, paths: List[str]):
        """
        Subscribe to current/actual value changes.

        Args:
            paths: List of VSS signal paths to subscribe to

        Yields:
            Dict[str, SignalValue] for each update
        """
        if not self._connected:
            raise RuntimeError("Not connected to KUKSA")

        # Subscribe to current values
        for updates in self._client.subscribe_current_values(paths):
            result = {}
            for path, dp in updates.items():
                if dp is not None:
                    result[path] = SignalValue(
                        path=path,
                        value=self._extract_value(dp),
                        mode=ActuatorMode.ACTUAL,
                        timestamp=dp.timestamp.seconds if hasattr(dp.timestamp, 'seconds') else None,
                        datapoint=dp
                    )
            if result:
                yield result

    async def validate_signal(self, signal: Signal, value: Any) -> bool:
        """Validate a value against signal specification"""
        # Type validation
        if signal.datatype == "bool" and not isinstance(value, bool):
            return False
        elif signal.datatype in ["float", "double"] and not isinstance(value, (int, float)):
            return False
        elif signal.datatype.startswith("int") or signal.datatype.startswith("uint"):
            if not isinstance(value, int):
                return False
        elif signal.datatype == "string" and not isinstance(value, str):
            return False

        # Range validation
        if isinstance(value, (int, float)):
            if signal.min is not None and value < signal.min:
                return False
            if signal.max is not None and value > signal.max:
                return False

        # Enum validation
        if signal.enum_values and value not in signal.enum_values:
            return False

        return True


class SyncKuksaClient:
    """Synchronous wrapper for KuksaClient"""
    
    def __init__(self, url: str = "127.0.0.1:55556", token: Optional[str] = None):
        self._async_client = KuksaClient(url, token)
        self._loop = asyncio.new_event_loop()
        
    def __enter__(self):
        self._loop.run_until_complete(self._async_client.connect())
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._loop.run_until_complete(self._async_client.disconnect())
        self._loop.close()
        
    def get_value(self, path: str, mode: Optional[ActuatorMode] = None) -> SignalValue:
        """Synchronous get_value"""
        return self._loop.run_until_complete(self._async_client.get_value(path, mode))
        
    def set_value(self, path: str, value: Any, mode: Optional[ActuatorMode] = None):
        """Synchronous set_value"""
        return self._loop.run_until_complete(self._async_client.set_value(path, value, mode))
        
    def get_values(self, paths: List[str]) -> Dict[str, SignalValue]:
        """Synchronous get_values"""
        return self._loop.run_until_complete(self._async_client.get_values(paths))
        
    def set_values(self, updates: Dict[str, Any]):
        """Synchronous set_values"""
        return self._loop.run_until_complete(self._async_client.set_values(updates))