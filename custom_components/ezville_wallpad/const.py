"""Constants for Ezville Wallpad integration."""
import logging

DOMAIN = "ezville_wallpad"
MANUFACTURER = "Pages in Korea (pages.kr)"
MODEL = "Ezville Wallpad"
DOCUMENTATION_URL = "https://github.com/pageskr/ha-ezville-wallpad"

# Logging helper
def _should_log_device(device_type):
    """Check if logging is enabled for this device type."""
    try:
        from . import LOGGING_ENABLED, LOGGING_DEVICE_TYPES
        if not LOGGING_ENABLED:
            return False
        # Check if device type or 'unknown' is in the list for unknown devices
        return device_type in LOGGING_DEVICE_TYPES or (device_type == "unknown" and "unknown" in LOGGING_DEVICE_TYPES)
    except:
        # If import fails, assume logging is disabled
        return False

def get_device_type_from_packet(packet):
    """Get device type from packet for logging."""
    if not packet or len(packet) < 2:
        return "unknown"
    
    device_id = packet[1]
    
    # Map device ID to device type
    device_id_map = {
        0x0E: "light",
        0x39: "plug",
        0x36: "thermostat",
        0x32: "fan",
        0x12: "gas",
        0x30: "energy",
        0x33: "elevator",
        0x40: "doorbell",
    }
    
    return device_id_map.get(device_id, "unknown")

def _log_to_file_only(logger, level, message, *args):
    """Log message only to file handlers."""
    # Create LogRecord manually
    record = logger.makeRecord(
        logger.name, level, "(unknown file)", 0,
        message, args, None
    )
    # Only send to file handlers (not to Home Assistant log)
    for handler in logger.handlers:
        if hasattr(handler, 'baseFilename'):  # File handler
            handler.emit(record)

def log_debug(logger, device_type, message, *args):
    """Log debug message if logging is enabled for the device type."""
    # Check if debug is enabled in Home Assistant for this logger
    if not logger.isEnabledFor(logging.DEBUG):
        return
    
    if _should_log_device(device_type):
        # Debug only goes to file when both HA debug and device logging are enabled
        _log_to_file_only(logger, logging.DEBUG, message, *args)

def log_info(logger, device_type, message, *args):
    """Log info message if logging is enabled for the device type."""
    if _should_log_device(device_type):
        # Info only goes to file
        _log_to_file_only(logger, logging.INFO, message, *args)

def log_warning(logger, device_type, message, *args):
    """Log warning message if logging is enabled for the device type."""
    if _should_log_device(device_type):
        # Warning goes to both file and HA log
        logger.warning(message, *args)

def log_error(logger, device_type, message, *args):
    """Log error message if logging is enabled for the device type."""
    if _should_log_device(device_type):
        # Error goes to both file and HA log
        logger.error(message, *args)

def log_system(logger, message, *args):
    """Log system message if general logging is enabled."""
    try:
        from . import LOGGING_ENABLED
        if not LOGGING_ENABLED:
            return
        # System messages only go to file
        _log_to_file_only(logger, logging.INFO, message, *args)
    except:
        pass

# Configuration keys
CONF_SERIAL_PORT = "serial_port"
CONF_HOST = "host"
CONF_PORT = "port"
CONF_CONNECTION_TYPE = "connection_type"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_MQTT_BROKER = "mqtt_broker"
CONF_MQTT_PORT = "mqtt_port"
CONF_MQTT_USERNAME = "mqtt_username"
CONF_MQTT_PASSWORD = "mqtt_password"
CONF_MQTT_TOPIC_RECV = "mqtt_topic_recv"
CONF_MQTT_TOPIC_SEND = "mqtt_topic_send"
CONF_MQTT_QOS = "mqtt_qos"
CONF_MQTT_STATE_SUFFIX = "mqtt_state_suffix"
CONF_MQTT_COMMAND_SUFFIX = "mqtt_command_suffix"

# Connection types
CONNECTION_TYPE_SERIAL = "serial"
CONNECTION_TYPE_SOCKET = "socket"
CONNECTION_TYPE_MQTT = "mqtt"

# Default values
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_PORT = 8899
DEFAULT_MQTT_PORT = 1883
DEFAULT_MAX_RETRY = 10
DEFAULT_MQTT_TOPIC_RECV = "ezville/wallpad/recv"
DEFAULT_MQTT_TOPIC_SEND = "ezville/wallpad/send"
DEFAULT_MQTT_QOS = 0
DEFAULT_MQTT_STATE_SUFFIX = "/state"
DEFAULT_MQTT_COMMAND_SUFFIX = "/command"

# RS485 Device definitions
RS485_DEVICE = {
    "light": {
        "state": {"id": 0x0E, "cmd": 0x81},
        "last": {},
        "power": {"id": 0x0E, "cmd": 0x41, "ack": 0xC1},
    },
    "plug": {
        "state": {"id": 0x39, "cmd": 0x81},
        "last": {},
        "power": {"id": 0x39, "cmd": 0x41, "ack": 0xC1},
    },
    "thermostat": {
        "state": {"id": 0x36, "cmd": 0x81},
        "last": {},
        "mode": {"id": 0x36, "cmd": 0x43, "ack": 0xC3},
        "target": {"id": 0x36, "cmd": 0x44, "ack": 0xC4},
        "away": {"id": 0x36, "cmd": 0x46, "ack": 0xC6},
    },
    "fan": {
        "state": {"id": 0x32, "cmd": 0x81},
        "last": {},
        "power": {"id": 0x32, "cmd": 0x41, "ack": 0xC1},
        "speed": {"id": 0x32, "cmd": 0x42, "ack": 0xC2},
        "mode": {"id": 0x32, "cmd": 0x43, "ack": 0xC3},
    },
    "gas": {
        "state": {"id": 0x12, "cmd": 0x81},
        "last": {},
        "close": {"id": 0x12, "cmd": 0x41, "ack": 0xC1},
    },
    "energy": {
        "state": {"id": 0x30, "cmd": 0x81},
        "last": {},
    },
    "elevator": {
        "state": {"id": 0x33, "cmd": 0x81},
        "last": {},
        "power": {"id": 0x33, "cmd": 0x41, "ack": 0xC1},
        "call": {"id": 0x33, "cmd": 0x43, "ack": 0xC3},
    },
    "doorbell": {
        "state": {"id": 0x40, "cmd": 0x81},
        "last": {},
        "call": {"id": 0x40, "cmd": 0x10, "ack": 0xC0},
        "ring": {"id": 0x40, "cmd": 0x13, "ack": 0xC3},
        "talk": {"id": 0x40, "cmd": 0x12, "ack": 0xC2},
        "open": {"id": 0x40, "cmd": 0x22, "ack": 0xC2},
        "cancel": {"id": 0x40, "cmd": 0x11, "ack": 0xC1},
    },
}

# State header mapping
STATE_HEADER = {
    prop["state"]["id"]: (device, prop["state"]["cmd"])
    for device, prop in RS485_DEVICE.items()
    if "state" in prop
}

# ACK header mapping
ACK_HEADER = {
    prop[cmd]["id"]: (device, prop[cmd]["ack"])
    for device, prop in RS485_DEVICE.items()
    for cmd, code in prop.items()
    if isinstance(code, dict) and "ack" in code
}

# Platform types
from homeassistant.const import Platform

PLATFORMS = [
    Platform.LIGHT,
    Platform.SWITCH, 
    Platform.SENSOR,
    Platform.CLIMATE,
    Platform.FAN,
    Platform.VALVE,
    Platform.BUTTON,
    Platform.BINARY_SENSOR,
]

# Device names
DEVICE_NAMES = {
    "doorbell": "Doorbell",
    "elevator": "Elevator",
    "energy": "Energy Meter",
    "gas": "Gas Valve",
    "light": "Light",
    "plug": "Plug",
    "thermostat": "Thermostat",
    "fan": "Ventilation Fan",
}

# Entity names
ENTITY_NAMES = {
    "energy_usage": "Energy Meter Usage",
    "gas_close": "Gas Valve Close",
    "fan_mode": "Ventilation Fan Mode",
}

# Packet examples (for debugging)
# Light state: f7 0e 11 81 03 01 00 00 e9 00  
# - 0e: light device ID
# - 11: room/group (upper 4 bits: group, lower 4 bits: room)
# - 81: state command
# - 03: data length (3 lights)
# - 01 00 00: light states (bit 0 = on/off)
# 
# Plug state: f7 39 11 81 06 00 00 00 00 00 00 6d 08
# - 39: plug device ID
# - 11: room/group 
# - 81: state command
# - 06: data length (2 plugs x 3 bytes each)
# - bytes 5-7: plug 1 data (power state + usage)
# - bytes 8-10: plug 2 data
#
# Thermostat state: f7 36 01 81 09 00 01 01 18 18 00 00 00 00 ea 02
# - 36: thermostat device ID
# - 01: room/group
# - 81: state command
# - 09: data length
# - bytes 5-13: thermostat data (mode, away, temps)
