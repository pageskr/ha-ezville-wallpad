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
    log_debug,
    log_info,
    log_warning,
    log_error,
    log_system,
    get_device_type_from_packet,
)

# Configure logger name to be shorter
_LOGGER = logging.getLogger("custom_components.ezville_wallpad.rs485")


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
        self._previous_mqtt_values = {}  # For MQTT deduplication
        self._processed_packets = set()  # Track processed packets to avoid duplicates
        
        # ACK mapping
        self._ack_map = defaultdict(lambda: defaultdict(dict))
        for device, prop in RS485_DEVICE.items():
            for cmd, code in prop.items():
                if isinstance(code, dict) and "ack" in code:
                    self._ack_map[code["id"]][code["cmd"]] = code["ack"]
        
        log_system(_LOGGER, "Initialized RS485 client with %s connection", connection_type)

    async def async_connect(self):
        """Connect to the device asynchronously."""
        if self._running:
            log_system(_LOGGER, "Client already running")
            return

        try:
            log_system(_LOGGER, "Connecting via %s", self.connection_type)
            
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
            
            self._thread = threading.Thread(target=self._message_loop, daemon=True)
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

    def _message_loop(self):
        """Main message processing loop."""
        log_system(_LOGGER, "Starting message loop")
        buffer = bytearray()
        
        # Set custom thread name for cleaner logs
        threading.current_thread().name = "paho-mqtt"
        
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
                        # For MQTT, special handling for multiple packets
                        if self.connection_type == CONNECTION_TYPE_MQTT:
                            self._process_mqtt_data(data)
                        else:
                            buffer.extend(data)
                            _LOGGER.debug("<== Received raw data: %s", data.hex())
                            self._process_buffer(buffer)
                except Exception:
                    pass
                
                time.sleep(0.01)
                
            except Exception as err:
                _LOGGER.error("Error in message loop: %s", err)
                time.sleep(1)
    
    def _process_mqtt_data(self, data: bytes):
        """Process MQTT data by splitting F7 packets."""
        messages = []
        current_msg = []
        started = False
        
        # Split by F7 markers
        for byte in data:
            if byte == 0xF7:  # New message start
                if started and current_msg:
                    messages.append(bytes(current_msg))
                    current_msg = []
                started = True
            if started:
                current_msg.append(byte)
        
        # Add the last message
        if current_msg:
            messages.append(bytes(current_msg))
        
        # Remove duplicate packets before processing
        unique_messages = []
        seen_packets = set()
        
        for msg in messages:
            if len(msg) < 4:
                continue
            
            # Use full packet as key for deduplication
            packet_key = msg.hex()
            if packet_key not in seen_packets:
                seen_packets.add(packet_key)
                unique_messages.append(msg)
        
        log_debug(_LOGGER, "unknown", "MQTT: Received %d packets, processing %d unique (removed %d duplicates)", 
                     len(messages), len(unique_messages), len(messages) - len(unique_messages))
        
        # Process each unique message
        for msg in unique_messages:
            # Create signature from first 4 bytes (8 hex characters)
            signature = msg[:4].hex()
            
            # Check if this is a new or changed packet
            if signature not in self._previous_mqtt_values or self._previous_mqtt_values[signature] != msg:
                hex_msg = ' '.join([f"{b:02x}" for b in msg])
                log_debug(_LOGGER, "unknown", "Converted hex message: %s", hex_msg)
                
                # Check if value has changed
                if signature in self._previous_mqtt_values:
                    log_debug(_LOGGER, "unknown", "Updated signature %s: %s", signature, ' '.join([f"{b:02x}" for b in msg[4:]]))
                else:
                    log_info(_LOGGER, "unknown", "Created signature %s: %s", signature, ' '.join([f"{b:02x}" for b in msg[4:]]))
                
                self._previous_mqtt_values[signature] = msg
                
                # Process the packet
                self._process_packet(msg)
            # else: packet is duplicate, skip processing

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
        
        # Step 1: Check if this is a known device type
        known_device_type = None
        for device_type, device_config in RS485_DEVICE.items():
            if "state" in device_config and device_config["state"]["id"] == device_id:
                known_device_type = device_type
                break
        
        # Get device type for logging
        device_type = known_device_type if known_device_type else "unknown"
        
        # Log packet analysis
        if device_type == "light":
            room_id = device_num & 0x0F
            log_info(_LOGGER, device_type, "Packet Analysis - Device ID: 0x%02X(Light), Room: 0x%02X(%d), Cmd: 0x%02X, Packet: %s", 
                         device_id, device_num, room_id, command, packet.hex())
        elif device_type == "plug":
            room_id = device_num >> 4
            log_info(_LOGGER, device_type, "Packet Analysis - Device ID: 0x%02X(Plug), Room: 0x%02X(%d), Cmd: 0x%02X, Packet: %s", 
                         device_id, device_num, room_id, command, packet.hex())
        elif device_type == "thermostat":
            log_info(_LOGGER, device_type, "Packet Analysis - Device ID: 0x%02X(Thermostat), Num: 0x%02X(%d), Cmd: 0x%02X, Packet: %s", 
                         device_id, device_num, device_num >> 4, command, packet.hex())
        else:
            log_info(_LOGGER, device_type, "Packet Analysis - Device ID: 0x%02X, Num: 0x%02X(%d), Cmd: 0x%02X, Packet: %s", 
                         device_id, device_num, device_num, command, packet.hex())
        
        # Step 2: Process based on device type
        if known_device_type:
            # Known device - check if it's a state packet
            if device_id in STATE_HEADER and command == STATE_HEADER[device_id][1]:
                # This is a state packet - process normally
                self._process_state_packet(known_device_type, packet)
            else:
                # This is a non-state packet for known device - create Cmd sensor
                log_info(_LOGGER, device_type, "=> Non-state packet for known device %s, creating Cmd sensor", known_device_type)
                self._handle_device_cmd_packet(known_device_type, packet)
        else:
            # Unknown device - create Unknown sensor
            log_info(_LOGGER, "unknown", "=> Unknown device packet: 0x%02X, creating Unknown sensor", device_id)
            self._handle_unknown_device(packet)
    
    def _process_state_packet(self, device_type: str, packet: bytes):
        """Process state packet for known device."""
        device_id = packet[1]
        device_num = packet[2]
        command = packet[3]
        
        # Parse state data based on device type
        state_data = self._parse_state(device_type, packet)
        
        # For light, plug, thermostat - they are handled inline below
        if device_type in ["light", "plug", "thermostat"]:
            # Device identification based on type
            if device_type == "light":
                # Extract room number from lower 4 bits
                room_id = int(device_num & 0x0F)
                
                if len(packet) > 4:
                    # Light count is 5th byte minus 1
                    light_count = packet[4] - 1
                    log_info(_LOGGER, device_type, "=> Light state: Room %d (device_num=0x%02X), Light count: %d", room_id, device_num, light_count)
                    
                    # Process each light in the room
                    for light_num in range(1, min(light_count + 1, 4)):  # Max 3 lights
                        # Light states start from 7th byte (index 6)
                        if len(packet) > 6 + light_num - 1:
                            device_key = f"{device_type}_{room_id}_{light_num}"
                            light_state = (packet[6 + light_num - 1] & 1) == 1
                            
                            individual_state = {"power": light_state}
                            
                            # Check if state changed
                            old_state_dict = self._device_states.get(device_key, {})
                            old_power = old_state_dict.get("power")
                            changes = []
                            
                            if old_power != light_state:
                                changes.append(f"switch: {'On' if old_power else 'Off' if old_power is not None else 'Unknown'} → {'On' if light_state else 'Off'}")
                            
                            if changes:
                                log_info(_LOGGER, device_type, "=> Light %d %d state: {'switch': '%s'}, changes: %s, entity_key: %s [UPDATED]", 
                                           room_id, light_num, "ON" if light_state else "OFF", ", ".join(changes), device_key)
                            else:
                                log_debug(_LOGGER, device_type, "=> Light %d %d state: {'switch': '%s'} [no change]", 
                                           room_id, light_num, "ON" if light_state else "OFF")
                            
                            # Check if new device
                            if device_key not in self._discovered_devices:
                                self._discovered_devices.add(device_key)
                                log_info(_LOGGER, device_type, "=> NEW DEVICE discovered: %s", device_key)
                                
                                # Call discovery callbacks
                                for callback in self._device_discovery_callbacks:
                                    try:
                                        callback(device_type, f"{room_id}_{light_num}")
                                    except Exception as err:
                                        log_error(_LOGGER, device_type, "Error in discovery callback: %s", err)
                            
                            # Update state
                            old_full_state = self._device_states.get(device_key, {}).copy()
                            self._device_states[device_key] = individual_state
                            
                            # Call callback
                            if device_type in self._callbacks:
                                log_debug(_LOGGER, device_type, "=> Calling callback for %s with key=%s, state=%s", 
                                             device_type, f"{room_id}_{light_num}", individual_state)
                                self._callbacks[device_type](device_type, f"{room_id}_{light_num}", 
                                                           individual_state)
                                log_debug(_LOGGER, device_type, "=> Callback completed for %s", device_key)
            
            elif device_type == "plug":
                # Extract room number from upper 4 bits
                room_id = int(device_num >> 4)
                
                if len(packet) > 5:
                    data_length = packet[4]
                    # Plug count is data length divided by 3
                    plug_count = int(data_length / 3)
                    log_info(_LOGGER, device_type, "=> Plug state: Room %d (device_num=0x%02X), Data length: %d bytes, Plug count: %d", room_id, device_num, data_length, plug_count)
                    
                    # Process each plug
                    for plug_num in range(1, min(plug_count + 1, 3)):  # Max 2 plugs
                        # Calculate index for this plug's data
                        base_idx = plug_num * 3 + 3  # Start from index for each plug
                        if len(packet) > base_idx + 2:
                            device_key = f"{device_type}_{room_id}_{plug_num}"
                            
                            # Parse plug data
                            # Power state is bit 4 of the first byte
                            power_state = (packet[base_idx] & 0x10) != 0
                            
                            # Power usage calculation
                            power_high = format((packet[base_idx] & 0x0F) | (packet[base_idx + 1] << 4) | (packet[base_idx + 2] >> 4), 'x')
                            power_decimal = format(packet[base_idx + 2] & 0x0F, 'x')
                            power_usage_str = f"{power_high}.{power_decimal}"
                            
                            # Convert to float
                            try:
                                power_usage = float(power_usage_str)
                            except:
                                power_usage = 0.0
                            
                            individual_state = {
                                "power": power_state,
                                "power_usage": power_usage
                            }
                            
                            # Check if state changed
                            old_state = self._device_states.get(device_key, {})
                            old_power = old_state.get("power")
                            old_usage = old_state.get("power_usage")
                            changes = []
                            
                            if old_power != power_state:
                                changes.append(f"switch: {'On' if old_power else 'Off' if old_power is not None else 'Unknown'} → {'On' if power_state else 'Off'}")
                            if old_usage != power_usage:
                                changes.append(f"power: {old_usage if old_usage is not None else 0} → {power_usage}")
                            
                            if changes:
                                log_info(_LOGGER, device_type, "=> Plug %d %d state: {'switch': '%s', 'power': %s}, changes: %s, entity_key: %s [UPDATED]", 
                                           room_id, plug_num, "ON" if power_state else "OFF", power_usage, ", ".join(changes), device_key)
                            else:
                                log_debug(_LOGGER, device_type, "=> Plug %d %d state: {'switch': '%s', 'power': %s} [no change]", 
                                           room_id, plug_num, "ON" if power_state else "OFF", power_usage)
                            
                            # Check if new device
                            if device_key not in self._discovered_devices:
                                self._discovered_devices.add(device_key)
                                log_info(_LOGGER, device_type, "=> NEW DEVICE discovered: %s", device_key)
                                
                                # Call discovery callbacks
                                for callback in self._device_discovery_callbacks:
                                    try:
                                        callback(device_type, f"{room_id}_{plug_num}")
                                    except Exception as err:
                                        log_error(_LOGGER, device_type, "Error in discovery callback: %s", err)
                            
                            # Update state
                            old_full_state = self._device_states.get(device_key, {}).copy()
                            self._device_states[device_key] = individual_state
                            
                            # Call callback
                            if device_type in self._callbacks:
                                log_debug(_LOGGER, device_type, "=> Calling callback for %s with key=%s, state=%s", 
                                             device_type, f"{room_id}_{plug_num}", individual_state)
                                self._callbacks[device_type](device_type, f"{room_id}_{plug_num}", 
                                                           individual_state)
                                log_debug(_LOGGER, device_type, "=> Callback completed for %s", device_key)
            
            elif device_type == "thermostat":
                # Special thermostat packet format
                if len(packet) > 4:
                    data_length = packet[4]
                    log_info(_LOGGER, device_type, "=> Thermostat state: Num %d (device_num=0x%02X), Data length: %d bytes", int(device_num >> 4), device_num, data_length)
                    
                    # Log raw data for analysis
                    if len(packet) > 5:
                        log_debug(_LOGGER, device_type, "=> Thermostat packet data: %s", 
                                     ' '.join([f'{b:02X}' for b in packet[5:]]))
                    
                    # Different parsing based on packet format
                    if data_length == 0x0D:  # Special format from log
                        # Format: f7 36 1f 81 0d 00 00 0f 00 00 05 1e 05 1c 05 1b 05 1b 5f cc
                        # bytes 5-9: header/status bytes
                        # bytes 10-11: temp pair 1 (target, current)
                        # bytes 12-13: temp pair 2
                        # bytes 14-15: temp pair 3
                        # bytes 16-17: temp pair 4
                        log_info(_LOGGER, device_type, "=> Special thermostat packet format detected")
                        
                        # Parse temperature pairs starting from byte 10
                        temp_start = 10
                        room_count = 0
                        
                        # Count valid temperature pairs
                        for i in range(4):
                            idx = temp_start + i * 2
                            if idx + 1 < len(packet) and (packet[idx] > 0 or packet[idx + 1] > 0):
                                room_count += 1
                        
                        log_info(_LOGGER, device_type, "=> Found %d thermostat(s) with temperature data", room_count)
                        
                        # Process each temperature pair
                        for i in range(room_count):
                            idx = temp_start + i * 2
                            if idx + 1 < len(packet):
                                # Thermostat room number is just the index + 1 (1, 2, 3, 4)
                                thermostat_room = i + 1
                                device_key = f"{device_type}_{thermostat_room}"
                                # Swap target/current based on actual data pattern
                                target_temp = packet[idx]
                                current_temp = packet[idx + 1]
                                
                                # Detect if temperatures seem swapped (current > 50 is unlikely)
                                if current_temp > 50 and target_temp < 50:
                                    target_temp, current_temp = current_temp, target_temp
                                
                                # Determine mode based on temperatures
                                # If target temp is 5 (min), assume it's off
                                mode = 0 if target_temp <= 5 else 1
                                
                                individual_state = {
                                    "mode": mode,
                                    "away": False,
                                    "current_temperature": current_temp,
                                    "target_temperature": target_temp
                                }
                                
                                # Check if state changed
                                old_state = self._device_states.get(device_key, {})
                                old_current = old_state.get("current_temperature")
                                old_target = old_state.get("target_temperature")
                                
                                if old_current != current_temp or old_target != target_temp:
                                    log_info(_LOGGER, device_type, "=> Thermostat %d - Current: %d°C → %d°C, Target: %d°C → %d°C, entity_key: %s [UPDATED]",
                                    thermostat_room, old_current if old_current is not None else 0, current_temp,
                                    old_target if old_target is not None else 0, target_temp, device_key)
                                else:
                                    log_debug(_LOGGER, device_type, "=> Thermostat %d - Current: %d°C, Target: %d°C [no change]",
                                               thermostat_room, current_temp, target_temp)
                                
                                # Device discovery and callback handling
                                if device_key not in self._discovered_devices:
                                    self._discovered_devices.add(device_key)
                                    log_info(_LOGGER, device_type, "=> NEW DEVICE discovered: %s", device_key)
                                    
                                    for callback in self._device_discovery_callbacks:
                                        try:
                                            callback(device_type, thermostat_room)
                                        except Exception as err:
                                            log_error(_LOGGER, device_type, "Error in discovery callback: %s", err)
                                
                                # Update state
                                old_full_state = self._device_states.get(device_key, {}).copy()
                                self._device_states[device_key] = individual_state
                                
                                if device_type in self._callbacks:
                                    log_debug(_LOGGER, device_type, "=> Calling callback for %s with key=%s, state=%s", 
                                                 device_type, thermostat_room, individual_state)
                                    self._callbacks[device_type](device_type, thermostat_room, individual_state)
                                    log_debug(_LOGGER, device_type, "=> Callback completed for %s", device_key)
                                    
                    else:
                        # Standard thermostat packet format
                        room_count = (data_length - 5) // 2 if data_length > 5 else 0
                        log_info(_LOGGER, device_type, "=> Standard format, calculated room count: %d", room_count)
                        
                        # Process each thermostat
                        for thermo_idx in range(0, min(room_count, 15)):
                            thermostat_room = thermo_idx + 1  # Room number is just 1, 2, 3, 4, etc.
                            device_key = f"{device_type}_{thermostat_room}"
                            
                            # Check if we have enough data
                            if len(packet) < 8 + thermo_idx * 2 + 3:
                                log_warning(_LOGGER, device_type, "Not enough data for thermostat room %d", thermostat_room)
                                continue
                            
                            # Extract state from standard format
                            mode_on = ((packet[6] & 0x1F) >> thermo_idx) & 1 if thermo_idx < 5 and len(packet) > 6 else False
                            away_on = ((packet[7] & 0x1F) >> thermo_idx) & 1 if thermo_idx < 5 and len(packet) > 7 else False
                            target_temp = packet[8 + thermo_idx * 2] if len(packet) > 8 + thermo_idx * 2 else 0
                            current_temp = packet[9 + thermo_idx * 2] if len(packet) > 9 + thermo_idx * 2 else 0
                            
                            individual_state = {
                                "mode": 1 if mode_on else 0,
                                "away": away_on,
                                "current_temperature": current_temp,
                                "target_temperature": target_temp
                            }
                            
                            # Check if state changed
                            old_state = self._device_states.get(device_key, {})
                            old_mode = old_state.get("mode")
                            old_current = old_state.get("current_temperature")
                            old_target = old_state.get("target_temperature")
                            
                            mode_value = 1 if mode_on else 0
                            if old_mode != mode_value or old_current != current_temp or old_target != target_temp:
                                log_info(_LOGGER, device_type, "=> Thermostat %d - Mode: %s → %s, Away: %s, Current: %d°C → %d°C, Target: %d°C → %d°C, entity_key: %s [UPDATED]",
                                           thermostat_room, "Heat" if old_mode == 1 else "Off" if old_mode == 0 else "UNKNOWN",
                                           "Heat" if mode_on else "Off", "On" if away_on else "Off",
                                           old_current if old_current is not None else 0, current_temp,
                                           old_target if old_target is not None else 0, target_temp, device_key)
                            else:
                                log_debug(_LOGGER, device_type, "=> Thermostat %d - Mode: %s, Away: %s, Current: %d°C, Target: %d°C [no change]",
                                           thermostat_room, "Heat" if mode_on else "Off", "On" if away_on else "Off",
                                           current_temp, target_temp)
                            
                            # Device discovery and callback handling
                            if device_key not in self._discovered_devices:
                                self._discovered_devices.add(device_key)
                                log_info(_LOGGER, device_type, "=> NEW DEVICE discovered: %s", device_key)
                                
                                for callback in self._device_discovery_callbacks:
                                    try:
                                        callback(device_type, thermostat_room)
                                    except Exception as err:
                                        log_error(_LOGGER, device_type, "Error in discovery callback: %s", err)
                            
                            # Update state
                            old_full_state = self._device_states.get(device_key, {}).copy()
                            self._device_states[device_key] = individual_state
                            
                            if device_type in self._callbacks:
                                log_debug(_LOGGER, device_type, "=> Calling callback for %s with key=%s, state=%s", 
                                             device_type, thermostat_room, individual_state)
                                self._callbacks[device_type](device_type, thermostat_room, individual_state)
                                log_debug(_LOGGER, device_type, "=> Callback completed for %s", device_key)
        
        elif state_data:  # Other device types that return state_data
            # Other device types (fan, gas, energy, elevator, doorbell) - single devices
            device_key = device_type  # No device_num suffix for single devices
            # Check if state changed
            old_state = self._device_states.get(device_key, {})
            state_changed = False
            change_desc = []
                
            for k, v in state_data.items():
                if old_state.get(k) != v:
                    state_changed = True
                    change_desc.append(f"{k}: {old_state.get(k)} → {v}")
            
            if state_changed:
                log_info(_LOGGER, device_type, "=> %s state: %s, changes: %s, entity_key: %s [UPDATED]", 
                           device_type.capitalize(), state_data, ", ".join(change_desc), device_key)
            else:
                log_debug(_LOGGER, device_type, "=> %s state: %s [no change]", 
                           device_type.capitalize(), state_data)
            
            # Check if new device
            if device_key not in self._discovered_devices:
                self._discovered_devices.add(device_key)
                log_info(_LOGGER, device_type, "=> NEW DEVICE discovered: %s", device_key)
                
                # Call discovery callbacks
                for callback in self._device_discovery_callbacks:
                    try:
                        callback(device_type, None)  # No device_id for single devices
                    except Exception as err:
                        log_error(_LOGGER, device_type, "Error in discovery callback: %s", err)
            
            # Update state
            old_full_state = self._device_states.get(device_key, {}).copy()
            self._device_states[device_key] = state_data
            
            # Call callback
            if device_type in self._callbacks:
                log_debug(_LOGGER, device_type, "=> Calling callback for %s with key=None, state=%s", 
                             device_type, state_data)
                self._callbacks[device_type](device_type, None, state_data)
                log_debug(_LOGGER, device_type, "=> Callback completed for %s", device_key)
    
    def _handle_device_cmd_packet(self, device_type: str, packet: bytes):
        """Handle non-state command packets for known devices."""
        if len(packet) < 4:
            return
        
        device_id = packet[1]
        device_num = packet[2]
        command = packet[3]
        
        # Skip 0x01 command (state request packet)
        if command == 0x01:
            log_debug(_LOGGER, device_type, "=> Skipping state request packet (0x01) for %s", device_type)
            return
        
        # Create sensor name based on device type
        if device_type in ["light", "plug"]:
            # Extract room number
            if device_type == "light":
                room_id = device_num & 0x0F
            else:  # plug
                room_id = device_num >> 4
            # Format: "Light 1 Cmd 0x??" or "Plug 1 Cmd 0x??"
            device_name = f"{device_type.title()} {room_id} Cmd 0x{command:02X}"
            device_key = f"{device_type}_{room_id}_cmd_{command:02X}"
        else:
            # Single devices (fan, gas, energy, elevator, doorbell, thermostat)
            if device_type == "fan":
                # Fan should display as Ventilation
                device_name = f"Ventilation Cmd 0x{command:02X}"
            else:
                device_name = f"{device_type.title()} Cmd 0x{command:02X}"
            device_key = f"{device_type}_cmd_{command:02X}"
        
        # Create state data for CMD packet
        state = {
            "device_id": f"0x{device_id:02X}",
            "device_num": f"0x{device_num:02X}",
            "command": f"0x{command:02X}",
            "data": packet.hex(),
            "packet_length": len(packet),
            "device_name": device_name,
            "base_device_type": device_type,
            "raw_data": ' '.join([f"{b:02x}" for b in packet[4:-2]]) if len(packet) > 4 else ""
        }
        
        log_debug(_LOGGER, device_type, "=> CMD packet for %s: %s", device_name, packet.hex())
        
        # Check if new cmd sensor (for discovery)
        if device_key not in self._discovered_devices:
            self._discovered_devices.add(device_key)
            log_info(_LOGGER, device_type, "=> NEW CMD SENSOR discovered: %s", device_key)
            
            # Call discovery callbacks with device_type_cmd to indicate CMD sensor
            for callback in self._device_discovery_callbacks:
                try:
                    # Pass device_type_cmd and device_key as device_id
                    callback(f"{device_type}_cmd", device_key)
                except Exception as err:
                    log_error(_LOGGER, device_type, "Error in discovery callback: %s", err)
        
        # For all CMD sensors, notify via callback without storing permanently
        # This prevents continuous updates from coordinator
        callback_type = f"{device_type}_cmd"
        if callback_type in self._callbacks:
            log_debug(_LOGGER, device_type, "=> Notifying CMD sensor %s", device_key)
            self._callbacks[callback_type](callback_type, device_key, state)
        else:
            # Try to use the device type callback
            if device_type in self._callbacks:
                log_debug(_LOGGER, device_type, "=> Notifying via device callback for CMD sensor %s", device_key)
                self._callbacks[device_type](callback_type, device_key, state)
    
    def _handle_unknown_device(self, packet: bytes):
        """Handle unknown devices and create entries for them."""
        if len(packet) < 4:
            return
        
        device_id = packet[1]
        device_num = packet[2]
        command = packet[3]
        
        # Create signature from first 4 bytes (8 hex characters)
        signature = packet[:4].hex()
        
        # Create unknown device key
        device_key = f"unknown_{signature}"
        device_type = "unknown"
        
        # Extract state data - store full packet data
        state = {
            "device_id": f"0x{device_id:02X}",
            "device_num": f"0x{device_num:02X}",
            "command": f"0x{command:02X}",
            "data": packet.hex(),  # Full packet data
            "signature": signature,
            "packet_length": len(packet)
        }
        
        # Add raw data for packets with payload
        if len(packet) > 4:
            state["raw_data"] = ' '.join([f"{b:02x}" for b in packet[4:-2]])
        
        # Check if new device/signature
        if device_key not in self._discovered_devices:
            self._discovered_devices.add(device_key)
            log_info(_LOGGER, "unknown", "=> NEW UNKNOWN DEVICE discovered: %s (signature: %s)", device_key, signature)
            
            # Call discovery callbacks with signature as device_id
            for callback in self._device_discovery_callbacks:
                try:
                    callback(device_type, signature)
                except Exception as err:
                    log_error(_LOGGER, "unknown", "Error in discovery callback: %s", err)
        
        # Check if state has changed - compare the actual packet data
        old_state = self._device_states.get(device_key, {})
        state_changed = old_state.get("data") != state.get("data")
        
        if state_changed:
            # Update state
            self._device_states[device_key] = state
            
            # Call callback if registered with signature as device_id
            if "unknown" in self._callbacks:
                log_info(_LOGGER, "unknown", "=> Calling callback for unknown with key=%s, state=%s", 
                             signature, state)
                self._callbacks["unknown"](device_type, signature, state)
                log_info(_LOGGER, "unknown", "=> Callback completed for %s", device_key)
            else:
                log_error(_LOGGER, "unknown", "=> No callback registered for unknown devices!")
            
            log_info(_LOGGER, "unknown", "=> Unknown device %s updated with state: %s", device_key, state)
        else:
            log_debug(_LOGGER, "unknown", "=> Unknown device %s state unchanged, skipping callback", device_key)

    def _parse_state(self, device_type: str, packet: bytes) -> Optional[Dict[str, Any]]:
        """Parse state packet based on device type."""
        state = {}
        
        if device_type == "fan":
            if len(packet) > 8:
                state["power"] = (packet[6] & 0x01) != 0
                state["speed"] = packet[7] if packet[7] <= 3 else 0
                mode_val = packet[8] & 0x03
                state["mode"] = "bypass" if mode_val == 0x01 else "heat" if mode_val == 0x03 else "unknown"
                log_debug(_LOGGER, device_type, "Fan state parsed: %s", state)
        
        elif device_type == "gas":
            if len(packet) > 6:
                valve_state = (packet[6] & 0x1F) >> 4
                state["closed"] = valve_state != 0x01  # 0x01 = open
                log_debug(_LOGGER, device_type, "Gas valve state parsed: %s", state)
        
        elif device_type == "energy":
            if len(packet) > 12:
                # Power reading (3 bytes from position 6-8)
                power_hex = packet[6:9].hex()
                state["power"] = int(power_hex) if power_hex.isdigit() else 0
                
                # Usage reading (3 bytes from position 10-12)
                if len(packet) > 12:
                    usage_hex = packet[10:13].hex()
                    state["usage"] = int(usage_hex) * 0.1 if usage_hex.isdigit() else 0
                
                # Current power reading from packet hex position 12:18
                # Convert to power value in W (hex value / 100)
                if len(packet) > 9:
                    # Extract bytes from positions 6-8 (3 bytes)
                    current_power_hex = packet.hex()[12:18]
                    try:
                        current_power_value = int(current_power_hex, 16) / 100.0
                        state["current_power"] = current_power_value
                    except:
                        state["current_power"] = 0.0
                        
                log_debug(_LOGGER, device_type, "Energy state parsed: %s", state)
        
        elif device_type == "elevator":
            if len(packet) > 6:
                state["status"] = packet[6] >> 4
                state["floor"] = packet[6] & 0x0F
                # Add device info and raw packet data
                state["device_id"] = f"0x{packet[1]:02X}"
                state["device_num"] = f"0x{packet[2]:02X}"
                state["raw_packet"] = packet
                log_debug(_LOGGER, device_type, "Elevator state parsed: %s", state)
        
        elif device_type == "doorbell":
            if len(packet) > 4:
                state["ring"] = packet[4] == 0x01
                state["ringing"] = False
                if len(packet) > 5:
                    state["ringing"] = packet[5] == 0x01
                # Check both ring state and ringing state
                state["ringing"] = state["ring"] or state["ringing"]
                log_debug(_LOGGER, device_type, "Doorbell state parsed: %s", state)
        
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
            device_num = (room_id << 4) | 0  # Room in upper 4 bits
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
            # For single devices (fan, gas, energy, elevator, doorbell), idn can be None or device number
            if idn is None:
                device_num = 0x01  # Default device number for single devices
            else:
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
        _LOGGER.info("Opening serial port %s with settings: 9600 8N1", self.port)
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
        _LOGGER.info("Connecting to socket %s:%s", self.host, self.port)
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
        _LOGGER.info("Connecting to MQTT broker %s:%s with QoS %d", 
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
                # Assume the payload is hex string or bytes
                if isinstance(msg.payload, bytes):
                    # Try to decode as hex string first
                    try:
                        hex_str = msg.payload.decode('utf-8')
                        # Remove any spaces, commas, newlines
                        hex_str = hex_str.replace(' ', '').replace(',', '').replace('\n', '').replace('\r', '')
                        data = bytes.fromhex(hex_str)
                        _LOGGER.debug("MQTT: Received %d bytes on %s, decoded to %d bytes", 
                                 len(msg.payload), msg.topic, len(data))
                    except:
                        # If not hex string, use raw bytes
                        data = msg.payload
                        _LOGGER.debug("MQTT: Received %d raw bytes on %s", 
                                 len(data), msg.topic)
                    
                    # Add data to buffer
                    self._recv_buf.extend(data)
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
            _LOGGER.info("Sent MQTT command to %s with QoS %d: %s", 
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

