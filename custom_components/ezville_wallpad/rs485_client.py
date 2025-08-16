"""RS485 communication client for Ezville Wallpad."""
import asyncio
import logging
import socket
import serial
import threading
import time
import json
from typing import Dict, Any, Optional, Callable, List
from collections import defaultdict
import paho.mqtt.client as mqtt

from .const import (
    CONNECTION_TYPE_SERIAL,
    CONNECTION_TYPE_SOCKET,
    CONNECTION_TYPE_MQTT,
    RS485_DEVICE,
    STATE_HEADER,
    ACK_HEADER,
    DEFAULT_MAX_RETRY,
    DEFAULT_MQTT_QOS,
)

_LOGGER = logging.getLogger(__name__)


class EzvilleRS485Client:
    """RS485 communication client."""

    def __init__(
        self,
        connection_type: str,
        serial_port: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        mqtt_broker: Optional[str] = None,
        mqtt_port: Optional[int] = None,
        mqtt_username: Optional[str] = None,
        mqtt_password: Optional[str] = None,
        mqtt_topic_recv: Optional[str] = None,
        mqtt_topic_send: Optional[str] = None,
        mqtt_state_suffix: Optional[str] = None,
        mqtt_command_suffix: Optional[str] = None,
        mqtt_qos: int = DEFAULT_MQTT_QOS,
        max_retry: int = DEFAULT_MAX_RETRY,
        dump_time: int = 0,
    ):
        """Initialize the RS485 client."""
        self.connection_type = connection_type
        self.serial_port = serial_port
        self.host = host
        self.port = port
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.mqtt_username = mqtt_username
        self.mqtt_password = mqtt_password
        self.mqtt_topic_recv = mqtt_topic_recv
        self.mqtt_topic_send = mqtt_topic_send
        self.mqtt_state_suffix = mqtt_state_suffix
        self.mqtt_command_suffix = mqtt_command_suffix
        self.mqtt_qos = mqtt_qos
        self.max_retry = max_retry
        self.dump_time = dump_time
        
        self._conn = None
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        self._callbacks = {}
        self._send_queue = {}
        self._ack_queue = {}
        self._device_states = {}
        self._discovered_devices = set()
        self._device_discovery_callbacks = []
        
        # ACK mapping
        self._ack_map = defaultdict(lambda: defaultdict(dict))
        for device, prop in RS485_DEVICE.items():
            for cmd, code in prop.items():
                if isinstance(code, dict) and "ack" in code:
                    self._ack_map[code["id"]][code["cmd"]] = code["ack"]
        
        _LOGGER.debug("Initialized RS485 client with %s connection", connection_type)

    async def async_connect(self):
        """Connect to the device asynchronously."""
        if self._running:
            _LOGGER.debug("Client already running")
            return

        try:
            _LOGGER.info("Connecting via %s", self.connection_type)
            
            # Use executor for blocking operations
            loop = asyncio.get_event_loop()
            
            if self.connection_type == CONNECTION_TYPE_SERIAL:
                _LOGGER.debug("Creating serial connection to %s", self.serial_port)
                self._conn = await loop.run_in_executor(
                    None, EzvilleSerial, self.serial_port
                )
            elif self.connection_type == CONNECTION_TYPE_SOCKET:
                _LOGGER.debug("Creating socket connection to %s:%s", self.host, self.port)
                self._conn = await loop.run_in_executor(
                    None, EzvilleSocket, self.host, self.port
                )
            elif self.connection_type == CONNECTION_TYPE_MQTT:
                _LOGGER.debug("Creating MQTT connection to %s:%s", self.mqtt_broker, self.mqtt_port)
                self._conn = EzvilleMqtt(
                    self.mqtt_broker, self.mqtt_port,
                    self.mqtt_username, self.mqtt_password,
                    self.mqtt_topic_recv, self.mqtt_topic_send,
                    self.mqtt_qos
                )
                # Connect asynchronously
                await self._conn.async_connect()
            else:
                raise ValueError(f"Invalid connection type: {self.connection_type}")

            self._running = True
            
            # Perform packet dump if requested
            if self.dump_time > 0:
                await self._dump_packets()
            
            self._thread = threading.Thread(target=self._communication_loop, daemon=True)
            self._thread.start()
            
            _LOGGER.info("Successfully connected to Ezville Wallpad via %s", self.connection_type)
            
        except Exception as err:
            _LOGGER.error("Failed to connect: %s", err)
            raise

    async def _dump_packets(self):
        """Dump packets for debugging."""
        _LOGGER.warning("Starting packet dump for %d seconds", self.dump_time)
        
        start_time = time.time()
        logs = []
        
        self._conn.set_timeout(2.0)
        
        try:
            while time.time() - start_time < self.dump_time:
                try:
                    data = self._conn.recv(128)
                except:
                    await asyncio.sleep(0.1)
                    continue

                if data:
                    for b in data:
                        if b == 0xF7 or len(logs) > 500:
                            if logs:
                                _LOGGER.info("DUMP: %s", "".join(logs))
                            logs = [f"{b:02X}"]
                        else:
                            logs.append(f",{b:02X}")
                            
            if logs:
                _LOGGER.info("DUMP: %s", "".join(logs))
                
        finally:
            self._conn.set_timeout(None)
            _LOGGER.warning("Packet dump completed")

    def test_connection(self) -> bool:
        """Test the connection."""
        try:
            _LOGGER.debug("Testing %s connection", self.connection_type)
            
            if self.connection_type == CONNECTION_TYPE_SERIAL:
                conn = EzvilleSerial(self.serial_port)
            elif self.connection_type == CONNECTION_TYPE_SOCKET:
                conn = EzvilleSocket(self.host, self.port)
            elif self.connection_type == CONNECTION_TYPE_MQTT:
                # For MQTT, just try to create client
                conn = EzvilleMqtt(
                    self.mqtt_broker, self.mqtt_port,
                    self.mqtt_username, self.mqtt_password,
                    self.mqtt_topic_recv, self.mqtt_topic_send,
                    self.mqtt_qos
                )
                # Test synchronous connection
                result = conn.test_connection()
                conn.close()
                _LOGGER.debug("MQTT connection test result: %s", result)
                return result
            else:
                _LOGGER.error("Invalid connection type: %s", self.connection_type)
                return False
            
            # Try to read some data with timeout
            conn.set_timeout(2.0)
            data = conn.recv(1)
            conn.close()
            _LOGGER.debug("Connection test successful")
            return True
            
        except Exception as err:
            _LOGGER.error("Test connection failed: %s", err)
            return False

    def close(self):
        """Close the connection."""
        _LOGGER.debug("Closing connection")
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        if self._conn:
            self._conn.close()
        _LOGGER.info("Connection closed")

    def register_callback(self, device_type: str, callback: Callable):
        """Register a callback for device updates."""
        self._callbacks[device_type] = callback
        _LOGGER.debug("Registered callback for %s", device_type)

    def register_device_discovery_callback(self, callback: Callable):
        """Register a callback for new device discovery."""
        self._device_discovery_callbacks.append(callback)
        _LOGGER.debug("Registered device discovery callback")

    def send_command(self, device: str, command: str, idn: str, payload: Any):
        """Send a command to a device."""
        if not self._running:
            _LOGGER.error("Client not running")
            return

        packet = self._create_command_packet(device, command, idn, payload)
        if packet:
            with self._lock:
                self._send_queue[packet] = time.time()
            _LOGGER.info("Queued command for %s %s: %s (payload: %s)", 
                        device, idn, packet.hex(), payload)

    def _communication_loop(self):
        """Main communication loop."""
        _LOGGER.debug("Starting communication loop")
        buffer = bytearray()
        
        while self._running:
            try:
                # Process send queue
                with self._lock:
                    for packet, timestamp in list(self._send_queue.items()):
                        if time.time() - timestamp > 0.1:  # Send after 100ms delay
                            self._conn.send(packet)
                            del self._send_queue[packet]
                            _LOGGER.info("==> Sent packet: %s", packet.hex())
                
                # Read incoming data
                try:
                    data = self._conn.recv(128)
                    if data:
                        buffer.extend(data)
                        _LOGGER.debug("<== Received raw data: %s", data.hex())
                        self._process_buffer(buffer)
                except Exception:
                    pass
                
                time.sleep(0.01)
                
            except Exception as err:
                _LOGGER.error("Error in communication loop: %s", err)
                time.sleep(1)

    def _process_buffer(self, buffer: bytearray):
        """Process received data buffer using ezville_wallpad.py logic."""
        processed_count = 0
        _LOGGER.debug("=== Processing buffer with %d bytes: %s ===", len(buffer), buffer.hex())
        
        while len(buffer) > 0:
            # Find the next F7 marker
            start_index = -1
            for i in range(len(buffer)):
                if buffer[i] == 0xF7:
                    start_index = i
                    break
            
            if start_index == -1:
                # No F7 found, clear buffer
                _LOGGER.debug("No F7 found in buffer, clearing %d bytes", len(buffer))
                buffer.clear()
                return
            
            # Remove data before F7
            if start_index > 0:
                _LOGGER.debug("Removing %d bytes before 0xF7: %s", start_index, buffer[0:start_index].hex())
                del buffer[0:start_index]
            
            # Skip consecutive 0xF7 at start
            while len(buffer) > 1 and buffer[0] == 0xF7 and buffer[1] == 0xF7:
                del buffer[0]
            
            # Need at least 4 bytes to determine packet type
            if len(buffer) < 4:
                _LOGGER.debug("Buffer too small (%d bytes), waiting for more data", len(buffer))
                return
            
            # Get headers
            header_1 = buffer[1]
            header_2 = buffer[2]
            header_3 = buffer[3]
            
            _LOGGER.debug("Analyzing packet - F7 %02X %02X %02X ...", header_1, header_2, header_3)
            
            # Determine packet length
            packet_length = 8  # Default length
            
            # Check if this is a state packet with variable length
            if header_1 in STATE_HEADER and header_3 == STATE_HEADER[header_1][1]:
                if len(buffer) < 5:
                    _LOGGER.debug("State packet but buffer too small for length byte")
                    return
                data_length = buffer[4]
                packet_length = 5 + data_length + 2  # F7 + 4 headers + data + checksum + add
                _LOGGER.debug("State packet: device=0x%02X, data_length=%d, total_length=%d", 
                             header_1, data_length, packet_length)
            else:
                # Standard 8-byte packet
                _LOGGER.debug("Standard packet: device=0x%02X, cmd=0x%02X, fixed length=8", 
                             header_1, header_3)
            
            # Find next F7 to ensure we don't include part of next packet
            next_f7 = -1
            for i in range(1, len(buffer)):
                if buffer[i] == 0xF7:
                    next_f7 = i
                    _LOGGER.debug("Found next F7 at position %d", next_f7)
                    break
            
            # Adjust packet length if next F7 found before expected end
            if next_f7 != -1 and next_f7 < packet_length:
                _LOGGER.debug("Adjusting packet length from %d to %d due to next F7", 
                             packet_length, next_f7)
                packet_length = next_f7
            
            # Check if we have complete packet
            if len(buffer) < packet_length:
                _LOGGER.debug("Incomplete packet, need %d bytes but have %d", packet_length, len(buffer))
                return
            
            # Extract packet
            packet = bytes(buffer[0:packet_length])
            del buffer[0:packet_length]
            
            _LOGGER.debug("Extracted packet [%d]: %s (length=%d)", 
                         processed_count + 1, packet.hex(), len(packet))
            
            # Verify checksum
            if not self._verify_checksum(packet):
                _LOGGER.warning("Checksum fail for packet: %s", packet.hex())
                continue
            
            # Process packet
            _LOGGER.info("<== Valid packet received [%d]: %s", processed_count + 1, packet.hex())
            self._process_packet(packet)
            processed_count += 1
            
            # Continue processing if there's more data
            if len(buffer) > 0:
                _LOGGER.debug("Buffer has %d more bytes, continuing to process", len(buffer))

    def _verify_checksum(self, packet: bytes) -> bool:
        """Verify packet checksum."""
        if len(packet) < 2:
            _LOGGER.warning("Packet too short for checksum: %d bytes", len(packet))
            return False
        
        # Log packet details for debugging
        _LOGGER.debug("Verifying checksum for packet: %s", packet.hex())
        _LOGGER.debug("  Packet length: %d bytes", len(packet))
        _LOGGER.debug("  Data bytes: %s", packet[:-2].hex())
        _LOGGER.debug("  Checksum byte: 0x%02X", packet[-2])
        _LOGGER.debug("  Add byte: 0x%02X", packet[-1])
        
        # Calculate checksum (XOR of all bytes except last two)
        checksum = 0
        for i, b in enumerate(packet[:-2]):
            old_checksum = checksum
            checksum ^= b
            _LOGGER.debug("  XOR step %d: 0x%02X ^ 0x%02X = 0x%02X", i, old_checksum, b, checksum)
        
        # Calculate ADD (sum of all bytes except last one)
        add = sum(packet[:-1]) & 0xFF
        _LOGGER.debug("  Sum of bytes[:-1]: %d (0x%02X)", sum(packet[:-1]), add)
        
        # Get expected values from packet
        expected_checksum = packet[-2]
        expected_add = packet[-1]
        
        # Check results
        checksum_ok = checksum == expected_checksum
        add_ok = add == expected_add
        
        _LOGGER.debug("Checksum verification:")
        _LOGGER.debug("  Checksum: calc=0x%02X, expected=0x%02X, %s", 
                     checksum, expected_checksum, "OK" if checksum_ok else "FAIL")
        _LOGGER.debug("  ADD: calc=0x%02X, expected=0x%02X, %s",
                     add, expected_add, "OK" if add_ok else "FAIL")
        
        if not checksum_ok or not add_ok:
            _LOGGER.warning("Checksum fail: %s | Checksum: calc=0x%02X exp=0x%02X %s | ADD: calc=0x%02X exp=0x%02X %s",
                           packet.hex(), checksum, expected_checksum, "OK" if checksum_ok else "FAIL",
                           add, expected_add, "OK" if add_ok else "FAIL")
        
        # Both checksum and add must match
        return checksum_ok and add_ok

    def _process_packet(self, packet: bytes):
        """Process a received packet with detailed logging."""
        if len(packet) < 4:
            _LOGGER.warning("Invalid packet length: %d bytes - %s", len(packet), packet.hex())
            return
        
        device_id = packet[1]
        device_num = packet[2]
        command = packet[3]
        
        _LOGGER.info("Packet Analysis - Device ID: 0x%02X, Num: 0x%02X(%d), Cmd: 0x%02X, Packet: %s", 
                     device_id, device_num, device_num, command, packet.hex())
        
        # Check if this is a state packet
        if device_id in STATE_HEADER:
            device_type, expected_cmd = STATE_HEADER[device_id]
            if command == expected_cmd:
                _LOGGER.info("=> State packet for device type: %s", device_type)
                
                # Parse state data based on device type
                state_data = self._parse_state(device_type, packet)
                if state_data:
                    # Device identification based on type
                    if device_type == "light":
                        # Extract room and device info
                        grp_id = device_num >> 4
                        rm_id = device_num & 0x0F
                        _LOGGER.info("=> Light state: Group %d, Room %d (device_num=0x%02X)", grp_id, rm_id, device_num)
                        
                        if len(packet) > 4:
                            light_count = packet[4]
                            _LOGGER.info("=> Light count in room: %d", light_count)
                            
                            # Process each light in the room
                            for light_num in range(1, min(light_count + 1, 4)):  # Max 3 lights
                                if len(packet) > 5 + light_num - 1:
                                    device_key = f"{device_type}_{rm_id}_{light_num}"
                                    light_state = (packet[5 + light_num - 1] & 1) == 1
                                    
                                    individual_state = {"power": light_state}
                                    _LOGGER.info("=> Light %s state: %s", device_key, 
                                               "ON" if light_state else "OFF")
                                    
                                    # Check if new device
                                    if device_key not in self._discovered_devices:
                                        self._discovered_devices.add(device_key)
                                        _LOGGER.info("=> NEW DEVICE discovered: %s", device_key)
                                        
                                        # Call discovery callbacks
                                        for callback in self._device_discovery_callbacks:
                                            try:
                                                callback(device_type, f"{rm_id}_{light_num}")
                                            except Exception as err:
                                                _LOGGER.error("Error in discovery callback: %s", err)
                                    
                                    # Update state
                                    self._device_states[device_key] = individual_state
                                    
                                    # Call callback
                                    if device_type in self._callbacks:
                                        self._callbacks[device_type](device_type, f"{rm_id}_{light_num}", 
                                                                   individual_state)
                    
                    elif device_type == "plug":
                        grp_id = device_num >> 4
                        rm_id = device_num & 0x0F
                        _LOGGER.info("=> Plug state: Group %d, Room %d (device_num=0x%02X)", grp_id, rm_id, device_num)
                        
                        if len(packet) > 5:
                            data_length = packet[4]
                            plug_count = data_length // 3  # 3 bytes per plug
                            _LOGGER.info("=> Data length: %d, Plug count: %d", data_length, plug_count)
                            
                            # Process each plug
                            for plug_num in range(1, min(plug_count + 1, 3)):  # Max 2 plugs
                                base_idx = 5 + (plug_num - 1) * 3  # Start from byte 5
                                if len(packet) > base_idx + 2:
                                    # Use room ID for device key, not group ID
                                    device_key = f"{device_type}_{rm_id}_{plug_num}"
                                    
                                    # Parse plug data
                                    byte1 = packet[base_idx]
                                    byte2 = packet[base_idx + 1]
                                    byte3 = packet[base_idx + 2]
                                    
                                    power_state = (byte1 & 0x10) != 0
                                    # Power usage calculation - need to verify this formula
                                    power_high = (byte1 & 0x0F) | (byte2 << 4)
                                    power_decimal = byte3 & 0x0F
                                    power_usage = float(f"{power_high}.{power_decimal}")
                                    
                                    individual_state = {
                                        "power": power_state,
                                        "power_usage": power_usage
                                    }
                                    _LOGGER.info("=> Plug %s state: %s, Power: %.1fW (bytes: %02X %02X %02X)", 
                                               device_key, "ON" if power_state else "OFF", power_usage,
                                               byte1, byte2, byte3)
                                    
                                    # Check if new device
                                    if device_key not in self._discovered_devices:
                                        self._discovered_devices.add(device_key)
                                        _LOGGER.info("=> NEW DEVICE discovered: %s", device_key)
                                        
                                        # Call discovery callbacks
                                        for callback in self._device_discovery_callbacks:
                                            try:
                                                callback(device_type, f"{rm_id}_{plug_num}")
                                            except Exception as err:
                                                _LOGGER.error("Error in discovery callback: %s", err)
                                    
                                    # Update state
                                    self._device_states[device_key] = individual_state
                                    
                                    # Call callback
                                    if device_type in self._callbacks:
                                        self._callbacks[device_type](device_type, f"{rm_id}_{plug_num}", 
                                                                   individual_state)
                    
                    elif device_type == "thermostat":
                        grp_id = device_num >> 4
                        rm_id = device_num & 0x0F
                        _LOGGER.info("=> Thermostat state: Group %d, Room %d (device_num=0x%02X)", grp_id, rm_id, device_num)
                        
                        if len(packet) > 4:
                            data_length = packet[4]
                            _LOGGER.info("=> Thermostat data_length: %d bytes", data_length)
                            
                            # Log raw data for analysis
                            if len(packet) > 5:
                                _LOGGER.debug("=> Thermostat packet data: %s", 
                                             ' '.join([f'{b:02X}' for b in packet[5:]]))
                            
                            # Different parsing based on packet format
                            if device_num == 0x1F and data_length == 0x0D:  # Special format from log
                                # Format: f7 36 1f 81 0d 00 00 0f 00 00 05 1e 05 1c 05 1b 05 1b 5f cc
                                # bytes 5-9: header/status bytes
                                # bytes 10-11: temp pair 1 (target, current)
                                # bytes 12-13: temp pair 2
                                # bytes 14-15: temp pair 3
                                # bytes 16-17: temp pair 4
                                _LOGGER.info("=> Special thermostat packet format detected")
                                
                                # Parse temperature pairs starting from byte 10
                                temp_start = 10
                                room_count = 0
                                
                                # Count valid temperature pairs
                                for i in range(4):
                                    idx = temp_start + i * 2
                                    if idx + 1 < len(packet) and (packet[idx] > 0 or packet[idx + 1] > 0):
                                        room_count += 1
                                
                                _LOGGER.info("=> Found %d thermostat(s) with temperature data", room_count)
                                
                                # Process each temperature pair
                                for i in range(room_count):
                                    idx = temp_start + i * 2
                                    if idx + 1 < len(packet):
                                        device_key = f"{device_type}_{i+1}"
                                        # Swap target/current based on actual data pattern
                                        target_temp = packet[idx]
                                        current_temp = packet[idx + 1]
                                        
                                        # Detect if temperatures seem swapped (current > 50 is unlikely)
                                        if current_temp > 50 and target_temp < 50:
                                            target_temp, current_temp = current_temp, target_temp
                                        
                                        individual_state = {
                                            "mode": 1,  # Default to heat mode
                                            "away": False,
                                            "current_temperature": current_temp,
                                            "target_temperature": target_temp
                                        }
                                        
                                        _LOGGER.info("=> Thermostat %s - Current: %d°C, Target: %d°C (idx=%d)",
                                                   device_key, current_temp, target_temp, idx)
                                        
                                        # Device discovery and callback handling
                                        if device_key not in self._discovered_devices:
                                            self._discovered_devices.add(device_key)
                                            _LOGGER.info("=> NEW DEVICE discovered: %s", device_key)
                                            
                                            for callback in self._device_discovery_callbacks:
                                                try:
                                                    callback(device_type, i+1)
                                                except Exception as err:
                                                    _LOGGER.error("Error in discovery callback: %s", err)
                                        
                                        self._device_states[device_key] = individual_state
                                        
                                        if device_type in self._callbacks:
                                            self._callbacks[device_type](device_type, i+1, individual_state)
                                        
                            else:
                                # Standard thermostat packet format
                                room_count = (data_length - 5) // 2 if data_length > 5 else 0
                                _LOGGER.info("=> Standard format, calculated room count: %d", room_count)
                                
                                # Process each thermostat
                                for thermo_id in range(1, min(room_count + 1, 16)):
                                    device_key = f"{device_type}_{thermo_id}"
                                    
                                    # Check if we have enough data
                                    if len(packet) < 8 + thermo_id * 2 + 1:
                                        _LOGGER.warning("Not enough data for thermostat %d", thermo_id)
                                        continue
                                    
                                    # Extract state from standard format
                                    mode_on = ((packet[6] & 0x1F) >> (thermo_id - 1)) & 1 if thermo_id <= 5 and len(packet) > 6 else False
                                    away_on = ((packet[7] & 0x1F) >> (thermo_id - 1)) & 1 if thermo_id <= 5 and len(packet) > 7 else False
                                    target_temp = packet[8 + thermo_id * 2] if len(packet) > 8 + thermo_id * 2 else 0
                                    current_temp = packet[9 + thermo_id * 2] if len(packet) > 9 + thermo_id * 2 else 0
                                    
                                    individual_state = {
                                        "mode": 1 if mode_on else 0,
                                        "away": away_on,
                                        "current_temperature": current_temp,
                                        "target_temperature": target_temp
                                    }
                                    
                                    _LOGGER.info("=> Thermostat %s - Mode: %s, Away: %s, Current: %d°C, Target: %d°C",
                                               device_key, "Heat" if mode_on else "Off", "On" if away_on else "Off",
                                               current_temp, target_temp)
                                    
                                    # Device discovery and callback handling
                                    if device_key not in self._discovered_devices:
                                        self._discovered_devices.add(device_key)
                                        _LOGGER.info("=> NEW DEVICE discovered: %s", device_key)
                                        
                                        for callback in self._device_discovery_callbacks:
                                            try:
                                                callback(device_type, thermo_id)
                                            except Exception as err:
                                                _LOGGER.error("Error in discovery callback: %s", err)
                                    
                                    self._device_states[device_key] = individual_state
                                    
                                    if device_type in self._callbacks:
                                        self._callbacks[device_type](device_type, thermo_id, individual_state)
                    
                    else:
                        # Other device types (fan, gas, energy, elevator, doorbell)
                        device_key = f"{device_type}_{device_num}"
                        _LOGGER.info("=> %s state for device %s: %s", 
                                   device_type.capitalize(), device_key, state_data)
                        
                        # Check if new device
                        if device_key not in self._discovered_devices:
                            self._discovered_devices.add(device_key)
                            _LOGGER.info("=> NEW DEVICE discovered: %s", device_key)
                            
                            # Call discovery callbacks
                            for callback in self._device_discovery_callbacks:
                                try:
                                    callback(device_type, device_num)
                                except Exception as err:
                                    _LOGGER.error("Error in discovery callback: %s", err)
                        
                        # Update state
                        self._device_states[device_key] = state_data
                        
                        # Call callback
                        if device_type in self._callbacks:
                            self._callbacks[device_type](device_type, device_num, state_data)
                
                return
            else:
                _LOGGER.debug("=> Device 0x%02X is state device but command 0x%02X != expected 0x%02X",
                             device_id, command, expected_cmd)
        
        # Check for ACK packets
        if device_id in ACK_HEADER:
            device_type, expected_ack = ACK_HEADER[device_id]
            if command == expected_ack:
                _LOGGER.info("=> ACK packet for %s command", device_type)
                return
            else:
                _LOGGER.debug("=> Device 0x%02X in ACK_HEADER but command 0x%02X != expected 0x%02X",
                             device_id, command, expected_ack)
        
        # Check for other known command patterns
        # Device 0x39 (plug) with command 0x01 might be a control response
        if device_id == 0x39 and command == 0x01:
            _LOGGER.info("=> Plug control response packet: device_num=0x%02X", device_num)
            return
        
        # Device 0x36 (thermostat) with command 0x01
        if device_id == 0x36 and command == 0x01:
            _LOGGER.info("=> Thermostat control response packet: device_num=0x%02X", device_num)
            return
        
        # Device 0x32 (fan) with command 0x01
        if device_id == 0x32 and command == 0x01:
            _LOGGER.info("=> Fan control response packet: device_num=0x%02X", device_num)
            return
        
        # Device 0x0E (light) with command 0x01
        if device_id == 0x0E and command == 0x01:
            _LOGGER.info("=> Light control response packet: device_num=0x%02X", device_num)
            return
        
        # Device 0x60 (unknown) with command 0x01
        if device_id == 0x60 and command == 0x01:
            _LOGGER.info("=> Unknown device 0x60 control packet: device_num=0x%02X", device_num)
            return
        
        # Unknown packet - log detailed info
        _LOGGER.warning("Unknown packet: %s | Device: 0x%02X | Num: 0x%02X (dec: %d) | Cmd: 0x%02X | State headers: %s | ACK headers: %s",
                       packet.hex(), device_id, device_num, device_num, command,
                       ','.join([f"0x{k:02X}" for k in STATE_HEADER.keys()]),
                       ','.join([f"0x{k:02X}" for k in ACK_HEADER.keys()]))

    def _parse_state(self, device_type: str, packet: bytes) -> Optional[Dict[str, Any]]:
        """Parse state packet based on device type."""
        state = {}
        
        if device_type == "fan":
            if len(packet) > 8:
                state["power"] = (packet[6] & 0x01) != 0
                state["speed"] = packet[7] if packet[7] <= 3 else 0
                mode_val = packet[8] & 0x03
                state["mode"] = "bypass" if mode_val == 0x01 else "heat" if mode_val == 0x03 else "unknown"
                _LOGGER.debug("Fan state parsed: %s", state)
        
        elif device_type == "gas":
            if len(packet) > 6:
                valve_state = (packet[6] & 0x1F) >> 4
                state["closed"] = valve_state != 0x01  # 0x01 = open
                _LOGGER.debug("Gas valve state parsed: %s", state)
        
        elif device_type == "energy":
            if len(packet) > 12:
                # Power reading (3 bytes from position 6-8)
                power_hex = packet[6:9].hex()
                state["power"] = int(power_hex) if power_hex.isdigit() else 0
                
                # Usage reading (3 bytes from position 10-12)
                if len(packet) > 12:
                    usage_hex = packet[10:13].hex()
                    state["usage"] = int(usage_hex) * 0.1 if usage_hex.isdigit() else 0
                _LOGGER.debug("Energy state parsed: %s", state)
        
        elif device_type == "elevator":
            if len(packet) > 6:
                status_val = packet[6] >> 4
                state["status"] = status_val
                state["floor"] = packet[6] & 0x0F
                _LOGGER.debug("Elevator state parsed: %s", state)
        
        elif device_type == "doorbell":
            if len(packet) > 4:
                # Check both ring state and ringing state
                ring_state = packet[4] == 0x01
                ringing_state = False
                if len(packet) > 5:
                    ringing_state = packet[5] == 0x01
                
                state["ring"] = ring_state
                state["ringing"] = ring_state or ringing_state  # For binary sensor
                _LOGGER.debug("Doorbell state parsed: ring=%s, ringing=%s", ring_state, ringing_state)
        
        # Note: light, plug, thermostat are handled in _process_packet directly
        
        return state

    def _create_command_packet(self, device: str, command: str, idn: str, payload: Any) -> Optional[bytes]:
        """Create command packet."""
        if device not in RS485_DEVICE:
            _LOGGER.error("Unknown device type: %s", device)
            return None
        
        device_info = RS485_DEVICE[device]
        if command not in device_info:
            _LOGGER.error("Unknown command %s for device %s", command, device)
            return None
        
        cmd_info = device_info[command]
        if not isinstance(cmd_info, dict):
            return None
        
        # Handle different IDN formats
        if device == "light":
            # idn format: "room_light" e.g., "1_2"
            parts = idn.split("_")
            if len(parts) == 2:
                room_id = int(parts[0])
                light_num = int(parts[1])
                device_num = (0 << 4) | room_id  # Group 0, Room N
                # Create packet
                packet = bytearray([0xF7, cmd_info["id"], device_num, cmd_info["cmd"], 0x03, light_num])
                packet.append(0x01 if payload else 0x00)
                packet.append(0x00)
            else:
                _LOGGER.error("Invalid light IDN format: %s", idn)
                return None
        
        elif device == "plug":
            # idn format: "room_plug" e.g., "1_2"
            parts = idn.split("_")
            if len(parts) == 2:
                room_id = int(parts[0])
                plug_num = int(parts[1])
                device_num = (room_id << 4) | 0  # Room as group
                # Create packet
                packet = bytearray([0xF7, cmd_info["id"], device_num, cmd_info["cmd"], 0x01])
                packet.append(0x11 if payload else 0x10)
            else:
                _LOGGER.error("Invalid plug IDN format: %s", idn)
                return None
        
        elif device == "thermostat":
            # idn is just the room number
            room_id = int(idn)
            device_num = (0 << 4) | room_id
            # Create packet
            packet = bytearray([0xF7, cmd_info["id"], device_num, cmd_info["cmd"], 0x01])
            if command == "mode":
                packet.append(0x01 if payload == "heat" else 0x00)
            elif command == "target":
                packet.append(int(payload) & 0xFF)
            elif command == "away":
                packet.append(0x01 if payload else 0x00)
            else:
                packet.append(0x00)
        
        else:
            # Other devices - simple format
            device_num = int(idn)
            packet = bytearray([0xF7, cmd_info["id"], device_num, cmd_info["cmd"]])
            
            # Add payload
            if isinstance(payload, bool):
                packet.append(0x01 if payload else 0x00)
            elif isinstance(payload, int):
                packet.append(payload & 0xFF)
            else:
                packet.append(0x00)
        
        # Pad to 8 bytes minimum
        while len(packet) < 8:
            packet.append(0x00)
        
        # Calculate checksum
        checksum = 0
        for b in packet[:-2]:
            checksum ^= b
        add = sum(packet[:-2]) & 0xFF
        packet[-2] = checksum
        packet[-1] = add
        
        _LOGGER.debug("Created command packet for %s %s: %s", device, idn, packet.hex())
        return bytes(packet)


class EzvilleSerial:
    """Serial connection wrapper."""
    
    def __init__(self, port: str):
        self.port = port
        self._serial = None
        self._connect()
    
    def _connect(self):
        """Connect to serial port."""
        _LOGGER.debug("Opening serial port %s", self.port)
        self._serial = serial.Serial(
            port=self.port,
            baudrate=9600,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=None
        )
        _LOGGER.info("Serial port %s opened successfully", self.port)
    
    def recv(self, count: int = 1) -> bytes:
        """Receive data."""
        return self._serial.read(count)
    
    def send(self, data: bytes):
        """Send data."""
        self._serial.write(data)
    
    def set_timeout(self, timeout: Optional[float]):
        """Set timeout."""
        self._serial.timeout = timeout
    
    def close(self):
        """Close connection."""
        if self._serial:
            self._serial.close()
            _LOGGER.debug("Serial port closed")


class EzvilleSocket:
    """Socket connection wrapper."""
    
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._socket = None
        self._recv_buf = bytearray()
        self._connect()
    
    def _connect(self):
        """Connect to socket."""
        _LOGGER.debug("Connecting to socket %s:%s", self.host, self.port)
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect((self.host, self.port))
        _LOGGER.info("Socket connection to %s:%s established", self.host, self.port)
    
    def recv(self, count: int = 1) -> bytes:
        """Receive data."""
        while len(self._recv_buf) < count:
            new_data = self._socket.recv(128)
            if not new_data:
                time.sleep(0.01)
                continue
            self._recv_buf.extend(new_data)
        
        result = self._recv_buf[:count]
        del self._recv_buf[:count]
        return bytes(result)
    
    def send(self, data: bytes):
        """Send data."""
        self._socket.sendall(data)
    
    def set_timeout(self, timeout: Optional[float]):
        """Set timeout."""
        self._socket.settimeout(timeout)
    
    def close(self):
        """Close connection."""
        if self._socket:
            self._socket.close()
            _LOGGER.debug("Socket connection closed")


class EzvilleMqtt:
    """MQTT connection wrapper."""
    
    def __init__(self, broker: str, port: int, username: Optional[str] = None, 
                 password: Optional[str] = None, topic_recv: str = None, 
                 topic_send: str = None, qos: int = 0):
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.topic_recv = topic_recv
        self.topic_send = topic_send
        self.qos = qos
        self._client = None
        self._recv_buf = bytearray()
        self._connected = False
        self._connect_event = threading.Event()
    
    async def async_connect(self):
        """Connect to MQTT broker asynchronously."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._connect)
    
    def _connect(self):
        """Connect to MQTT broker."""
        _LOGGER.debug("Connecting to MQTT broker %s:%s with QoS %d", 
                     self.broker, self.port, self.qos)
        
        self._client = mqtt.Client()
        
        if self.username and self.password:
            self._client.username_pw_set(self.username, self.password)
            _LOGGER.debug("MQTT authentication configured")
        
        # Set callbacks
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect
        
        # Connect to broker
        self._client.connect(self.broker, self.port, keepalive=60)
        self._client.loop_start()
        
        # Wait for connection with timeout
        if not self._connect_event.wait(timeout=5):
            _LOGGER.error("MQTT connection timeout")
            raise Exception(f"Failed to connect to MQTT broker {self.broker}:{self.port}")
        
        _LOGGER.info("Connected to MQTT broker successfully")
    
    def test_connection(self) -> bool:
        """Test MQTT connection."""
        try:
            _LOGGER.debug("Testing MQTT connection to %s:%s", self.broker, self.port)
            test_client = mqtt.Client()
            if self.username and self.password:
                test_client.username_pw_set(self.username, self.password)
            
            # Try to connect
            test_client.connect(self.broker, self.port, keepalive=60)
            test_client.disconnect()
            _LOGGER.debug("MQTT test connection successful")
            return True
        except Exception as err:
            _LOGGER.error("MQTT test connection failed: %s", err)
            return False
    
    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback."""
        if rc == 0:
            _LOGGER.info("Connected to MQTT broker with result code %d", rc)
            self._connected = True
            self._connect_event.set()
            # Subscribe to receive topic
            if self.topic_recv:
                client.subscribe(self.topic_recv, qos=self.qos)
                _LOGGER.info("Subscribed to topic: %s with QoS %d", self.topic_recv, self.qos)
        else:
            _LOGGER.error("Failed to connect to MQTT broker, rc=%d", rc)
            self._connect_event.set()
    
    def _on_message(self, client, userdata, msg):
        """MQTT message callback."""
        try:
            # Parse the message payload
            if msg.topic == self.topic_recv:
                _LOGGER.debug("MQTT MSG on %s: %d bytes", msg.topic, len(msg.payload))
                
                # Assume the payload is hex string or bytes
                if isinstance(msg.payload, bytes):
                    # Try to decode as hex string first
                    try:
                        hex_str = msg.payload.decode('utf-8')
                        # Remove any spaces, commas, newlines
                        hex_str = hex_str.replace(' ', '').replace(',', '').replace('\n', '').replace('\r', '')
                        data = bytes.fromhex(hex_str)
                        _LOGGER.debug("MQTT Decoded hex string to %d bytes: %s", len(data), data.hex())
                    except:
                        # If not hex string, use raw bytes
                        data = msg.payload
                        _LOGGER.debug("MQTT Using raw bytes: %d bytes", len(data))
                    
                    # Add data to buffer
                    self._recv_buf.extend(data)
                    _LOGGER.debug("MQTT Buffer now has %d bytes", len(self._recv_buf))
        except Exception as err:
            _LOGGER.error("Error processing MQTT message: %s", err)
    
    def _on_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback."""
        self._connected = False
        if rc != 0:
            _LOGGER.warning("Unexpected MQTT disconnection, rc=%d", rc)
        else:
            _LOGGER.debug("MQTT disconnected normally")
    
    def recv(self, count: int = 1) -> bytes:
        """Receive data."""
        # Non-blocking receive for MQTT
        if len(self._recv_buf) >= count:
            result = self._recv_buf[:count]
            del self._recv_buf[:count]
            return bytes(result)
        else:
            # Return what we have
            result = bytes(self._recv_buf)
            self._recv_buf.clear()
            return result
    
    def send(self, data: bytes):
        """Send data."""
        if self._connected and self.topic_send:
            # Send as hex string
            hex_str = data.hex().upper()
            # Format as comma-separated hex values
            formatted = ','.join([hex_str[i:i+2] for i in range(0, len(hex_str), 2)])
            self._client.publish(self.topic_send, formatted, qos=self.qos)
            _LOGGER.debug("Sent MQTT data to %s with QoS %d: %s", 
                        self.topic_send, self.qos, formatted)
    
    def set_timeout(self, timeout: Optional[float]):
        """Set timeout (not fully implemented for MQTT)."""
        # MQTT doesn't have a direct timeout setting like serial/socket
        pass
    
    def close(self):
        """Close connection."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False
            _LOGGER.debug("MQTT connection closed")
