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
            # Build the full path with mode suffix for actuators
            full_path = self._build_path(path, mode)
            
            # Get current value
            response = self._client.get_current_values([full_path])
            
            if full_path in response:
                dp = response[full_path]
                return SignalValue(
                    path=path,
                    value=self._extract_value(dp),
                    mode=mode,
                    timestamp=dp.timestamp.seconds if hasattr(dp.timestamp, 'seconds') else None,
                    datapoint=dp
                )
            else:
                raise ValueError(f"Signal {full_path} not found")
                
        except Exception as e:
            logger.error(f"Failed to get value for {path}: {e}")
            raise
    
    async def set_value(self, path: str, value: Any, mode: Optional[ActuatorMode] = None):
        """
        Set a signal value.
        
        Args:
            path: VSS signal path
            value: Value to set
            mode: For actuators, specify TARGET or ACTUAL (default: TARGET)
        """
        if not self._connected:
            await self.connect()
            
        try:
            # Build the full path with mode suffix for actuators  
            full_path = self._build_path(path, mode, default_mode=ActuatorMode.TARGET)
            
            # Set value
            updates = {full_path: self._build_datapoint(value)}
            self._client.set_current_values(updates)
            
            logger.debug(f"Set {full_path} = {value}")
            
        except Exception as e:
            logger.error(f"Failed to set value for {path}: {e}")
            raise
    
    async def get_values(self, paths: List[str]) -> Dict[str, SignalValue]:
        """Get multiple signal values in one call"""
        if not self._connected:
            await self.connect()
            
        try:
            # Get all values
            response = self._client.get_current_values(paths)
            
            # Convert to SignalValue objects
            result = {}
            for path, dp in response.items():
                # Extract base path and mode
                base_path, mode = self._parse_path(path)
                result[base_path] = SignalValue(
                    path=base_path,
                    value=self._extract_value(dp),
                    mode=mode,
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
            # Build datapoints
            datapoints = {}
            for path, value in updates.items():
                # Handle actuator paths with mode
                if isinstance(value, dict) and 'value' in value:
                    full_path = self._build_path(path, value.get('mode'), ActuatorMode.TARGET)
                    datapoints[full_path] = self._build_datapoint(value['value'])
                else:
                    datapoints[path] = self._build_datapoint(value)
                    
            # Set all values
            self._client.set_current_values(datapoints)
            
            logger.debug(f"Set {len(datapoints)} values")
            
        except Exception as e:
            logger.error(f"Failed to set values: {e}")
            raise
    
    def _build_path(self, base_path: str, mode: Optional[ActuatorMode], 
                    default_mode: Optional[ActuatorMode] = None) -> str:
        """Build full VSS path with actuator mode suffix"""
        if mode:
            return f"{base_path}.{mode.value.capitalize()}"
        elif default_mode:
            return f"{base_path}.{default_mode.value.capitalize()}"
        return base_path
    
    def _parse_path(self, full_path: str) -> tuple[str, Optional[ActuatorMode]]:
        """Parse VSS path to extract base path and actuator mode"""
        if full_path.endswith('.Target'):
            return full_path[:-7], ActuatorMode.TARGET
        elif full_path.endswith('.Actual'):
            return full_path[:-7], ActuatorMode.ACTUAL
        return full_path, None
    
    def _extract_value(self, datapoint: Datapoint) -> Any:
        """Extract value from KUKSA datapoint"""
        # Datapoint has a direct value attribute
        return datapoint.value
    
    def _build_datapoint(self, value: Any) -> Datapoint:
        """Build KUKSA datapoint from value"""
        # Datapoint constructor takes the value directly
        return Datapoint(value)
    
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