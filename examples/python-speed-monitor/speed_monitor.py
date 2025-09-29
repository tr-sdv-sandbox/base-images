#!/usr/bin/env python3
"""
Example SDV User Function: Speed Monitor
Monitors vehicle speed and triggers alerts for speeding
"""
import os
import sys
import time
import asyncio
from kuksa_client.grpc import VSSClient
from kuksa_client.grpc import VSSClientError

class SpeedMonitor:
    def __init__(self):
        self.client = None
        self.speed_limit = float(os.getenv('SPEED_LIMIT', '120'))  # km/h
        self.kuksa_address = os.getenv('KUKSA_ADDRESS', 'localhost')
        self.kuksa_port = int(os.getenv('KUKSA_PORT', '55555'))
        self.use_tls = os.getenv('KUKSA_TLS', 'false').lower() == 'true'
        
    async def connect(self):
        """Connect to KUKSA.val databroker"""
        try:
            print(f"Connecting to KUKSA.val at {self.kuksa_address}:{self.kuksa_port}")
            self.client = VSSClient(
                host=self.kuksa_address,
                port=self.kuksa_port,
                ensure_startup_connection=False
            )
            self.client.connect()
            print("Connected to KUKSA.val databroker")
            return True
        except Exception as e:
            print(f"Failed to connect to KUKSA.val: {e}")
            return False
    
    async def monitor_speed(self):
        """Subscribe to vehicle speed and monitor for speeding"""
        try:
            # Subscribe to vehicle speed  
            from kuksa_client.grpc import SubscribeEntry, View, Field
            entries = [
                SubscribeEntry('Vehicle.Speed', View.FIELDS, (Field.VALUE,))
            ]
            
            for updates in self.client.subscribe(entries=entries):
                for update in updates:
                    entry = update.entry
                    if entry.path == 'Vehicle.Speed' and hasattr(entry, 'value') and entry.value:
                        speed = entry.value.value
                        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                        
                        print(f"[{timestamp}] Current speed: {speed:.1f} km/h")
                        
                        if speed > self.speed_limit:
                            print(f"⚠️  SPEED ALERT: {speed:.1f} km/h exceeds limit of {self.speed_limit} km/h")
                            # Here you could trigger additional actions:
                            # - Log to a database
                            # - Send notifications
                            # - Update other vehicle signals
                        
        except VSSClientError as e:
            print(f"VSS Client error: {e}")
        except Exception as e:
            print(f"Error monitoring speed: {e}")
    
    async def run(self):
        """Main run loop with reconnection logic"""
        while True:
            if await self.connect():
                try:
                    await self.monitor_speed()
                except Exception as e:
                    print(f"Monitoring error: {e}")
                finally:
                    if self.client:
                        await self.client.disconnect()
            
            print("Reconnecting in 5 seconds...")
            await asyncio.sleep(5)

async def main():
    monitor = SpeedMonitor()
    await monitor.run()

if __name__ == "__main__":
    print("Speed Monitor User Function Starting...")
    print(f"Speed limit set to: {os.getenv('SPEED_LIMIT', '120')} km/h")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSpeed monitor stopped by user")
        sys.exit(0)