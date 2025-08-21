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