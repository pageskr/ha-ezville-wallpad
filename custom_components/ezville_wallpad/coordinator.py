"""Data update coordinator for Ezville Wallpad."""
import logging
import asyncio
from datetime import timedelta
from typing import Any, Dict, Optional, Callable
from logging.handlers import TimedRotatingFileHandler

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN, 
    RS485_DEVICE,
    CONNECTION_TYPE_MQTT,
    MANUFACTURER,
    MODEL,
    DOCUMENTATION_URL
)
from .rs485_client import EzvilleRS485Client

_LOGGER = logging.getLogger(__name__)


class EzvilleWallpadCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Ezville Wallpad data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry,
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
        mqtt_qos: int = 0,
        update_interval: timedelta = timedelta(seconds=30),
    ):
        """Initialize the coordinator."""
        # For MQTT, we don't need regular polling
        if connection_type == CONNECTION_TYPE_MQTT:
            update_interval = None  # Disable polling for MQTT
            _LOGGER.debug("MQTT mode: Disabling polling, using event-driven updates")
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )
        
        self.config_entry = config_entry
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
        
        # Get options from config entry
        self.options = config_entry.options
        self.capabilities = self.options.get("capabilities", [
            "light", "plug", "thermostat", "fan", "gas", 
            "energy", "elevator", "doorbell"
        ])
        
        _LOGGER.info("Initializing coordinator with capabilities: %s", self.capabilities)
        
        # Initialize RS485 client with options
        self.client = EzvilleRS485Client(
            connection_type=connection_type,
            serial_port=serial_port,
            host=host,
            port=port,
            mqtt_broker=mqtt_broker,
            mqtt_port=mqtt_port,
            mqtt_username=mqtt_username,
            mqtt_password=mqtt_password,
            mqtt_topic_recv=mqtt_topic_recv,
            mqtt_topic_send=mqtt_topic_send,
            mqtt_state_suffix=mqtt_state_suffix,
            mqtt_command_suffix=mqtt_command_suffix,
            mqtt_qos=mqtt_qos,
            max_retry=self.options.get("max_retry", 10),
            dump_time=self.options.get("dump_time", 0),
        )
        
        # Device data storage
        self.devices = {}
        self._entity_callbacks = {}
        self._platform_loaded = set()
        self._platforms_to_load = set()
        
        # Initialize default devices for testing (especially for MQTT)
        if connection_type == CONNECTION_TYPE_MQTT:
            self._initialize_default_devices()
        
        # Register device discovery callback
        self.client.register_device_discovery_callback(self._on_device_discovered)
        
        # Register device callbacks only for enabled capabilities
        for device_type in self.capabilities:
            self.client.register_callback(device_type, self._device_update_callback)
            _LOGGER.debug("Registered callback for device type: %s", device_type)

    def _initialize_default_devices(self):
        """Initialize default devices for enabled capabilities."""
        _LOGGER.info("Initializing default devices for initial setup")
        
        # Create initial devices according to requirements
        if "doorbell" in self.capabilities:
            device_key = "doorbell_1"
            self.devices[device_key] = {
                "device_type": "doorbell",
                "device_id": 1,
                "name": "Doorbell",
                "state": {"ring": False}
            }
            _LOGGER.debug("Created default doorbell: %s", device_key)
        
        if "elevator" in self.capabilities:
            device_key = "elevator_1"
            self.devices[device_key] = {
                "device_type": "elevator",
                "device_id": 1,
                "name": "Elevator",
                "state": {"status": 0, "floor": 1}
            }
            _LOGGER.debug("Created default elevator: %s", device_key)
        
        if "energy" in self.capabilities:
            device_key = "energy_0"
            self.devices[device_key] = {
                "device_type": "energy",
                "device_id": 0,
                "name": "Energy Meter",
                "state": {"power": 0, "usage": 0}
            }
            _LOGGER.debug("Created default energy meter: %s", device_key)
        
        if "gas" in self.capabilities:
            device_key = "gas_1"
            self.devices[device_key] = {
                "device_type": "gas",
                "device_id": 1,
                "name": "Gas Valve",
                "state": {"closed": True}
            }
            _LOGGER.debug("Created default gas valve: %s", device_key)
        
        if "light" in self.capabilities:
            # Create Light 1 with 3 components
            for light_num in range(1, 4):
                device_key = f"light_1_{light_num}"
                self.devices[device_key] = {
                    "device_type": "light",
                    "device_id": f"1_{light_num}",
                    "room_id": 1,
                    "light_num": light_num,
                    "name": f"Light 1 {light_num}",
                    "state": {"power": False}
                }
                _LOGGER.debug("Created default light: %s", device_key)
        
        if "plug" in self.capabilities:
            # Create Plug 1 with 2 components
            for plug_num in range(1, 3):
                device_key = f"plug_1_{plug_num}"
                self.devices[device_key] = {
                    "device_type": "plug",
                    "device_id": f"1_{plug_num}",
                    "room_id": 1,
                    "plug_num": plug_num,
                    "name": f"Plug 1 {plug_num}",
                    "state": {"power": False, "power_usage": 0}
                }
                _LOGGER.debug("Created default plug: %s", device_key)
        
        if "thermostat" in self.capabilities:
            device_key = "thermostat_1"
            self.devices[device_key] = {
                "device_type": "thermostat",
                "device_id": 1,
                "room_id": 1,
                "name": "Thermostat 1",
                "state": {
                    "mode": 0,
                    "current_temperature": 22,
                    "target_temperature": 24
                }
            }
            _LOGGER.debug("Created default thermostat: %s", device_key)
        
        if "fan" in self.capabilities:
            device_key = "fan_1"
            self.devices[device_key] = {
                "device_type": "fan",
                "device_id": 1,
                "name": "Ventilation Fan",
                "state": {"power": False, "speed": 0, "mode": "bypass"}
            }
            _LOGGER.debug("Created default ventilation fan: %s", device_key)
        
        _LOGGER.info("Created %d default devices", len(self.devices))
        
        # Determine which platforms need to be loaded
        self._determine_platforms_to_load()

    def _determine_platforms_to_load(self):
        """Determine which platforms need to be loaded based on devices."""
        from homeassistant.const import Platform
        
        for device_info in self.devices.values():
            device_type = device_info["device_type"]
            
            if device_type == "light":
                self._platforms_to_load.add(Platform.LIGHT)
            elif device_type == "plug":
                self._platforms_to_load.add(Platform.SWITCH)
                self._platforms_to_load.add(Platform.SENSOR)
            elif device_type == "thermostat":
                self._platforms_to_load.add(Platform.CLIMATE)
            elif device_type == "fan":
                self._platforms_to_load.add(Platform.FAN)
            elif device_type == "gas":
                self._platforms_to_load.add(Platform.VALVE)
            elif device_type == "energy":
                self._platforms_to_load.add(Platform.SENSOR)
            elif device_type == "elevator":
                self._platforms_to_load.add(Platform.BUTTON)
            elif device_type == "doorbell":
                self._platforms_to_load.add(Platform.BUTTON)
                self._platforms_to_load.add(Platform.BINARY_SENSOR)
        
        _LOGGER.info("Platforms to load: %s", self._platforms_to_load)

    def _on_device_discovered(self, device_type: str, device_id: int):
        """Handle new device discovery."""
        if device_type not in self.capabilities:
            _LOGGER.debug("Ignoring discovered device %s_%d (not in capabilities)", 
                         device_type, device_id)
            return
        
        device_key = f"{device_type}_{device_id}"
        
        if device_key not in self.devices:
            _LOGGER.info("Discovered new device: %s", device_key)
            
            # Create device entry
            self.devices[device_key] = {
                "device_type": device_type,
                "device_id": device_id,
                "name": f"{device_type.title()} {device_id}",
                "state": {}
            }
            
            # Check if platform needs to be loaded
            self._check_and_load_platform(device_type)
            
            # Notify that data has been updated
            self.async_set_updated_data(self.devices)

    def _check_and_load_platform(self, device_type: str):
        """Check if platform needs to be loaded for device type."""
        from homeassistant.const import Platform
        
        platforms_needed = set()
        
        if device_type == "light" and Platform.LIGHT not in self._platform_loaded:
            platforms_needed.add(Platform.LIGHT)
        elif device_type == "plug":
            if Platform.SWITCH not in self._platform_loaded:
                platforms_needed.add(Platform.SWITCH)
            if Platform.SENSOR not in self._platform_loaded:
                platforms_needed.add(Platform.SENSOR)
        elif device_type == "thermostat" and Platform.CLIMATE not in self._platform_loaded:
            platforms_needed.add(Platform.CLIMATE)
        elif device_type == "fan" and Platform.FAN not in self._platform_loaded:
            platforms_needed.add(Platform.FAN)
        elif device_type == "gas" and Platform.VALVE not in self._platform_loaded:
            platforms_needed.add(Platform.VALVE)
        elif device_type == "energy" and Platform.SENSOR not in self._platform_loaded:
            platforms_needed.add(Platform.SENSOR)
        elif device_type in ["elevator", "doorbell"]:
            if Platform.BUTTON not in self._platform_loaded:
                platforms_needed.add(Platform.BUTTON)
            if device_type == "doorbell" and Platform.BINARY_SENSOR not in self._platform_loaded:
                platforms_needed.add(Platform.BINARY_SENSOR)
        
        if platforms_needed:
            _LOGGER.info("Loading platforms for %s: %s", device_type, platforms_needed)
            # Schedule platform loading
            for platform in platforms_needed:
                self._platform_loaded.add(platform)
                self.hass.async_create_task(
                    self.hass.config_entries.async_forward_entry_setup(
                        self.config_entry, platform
                    )
                )

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from the wallpad."""
        # For MQTT, we don't poll - data comes via callbacks
        if self.connection_type == CONNECTION_TYPE_MQTT:
            _LOGGER.debug("MQTT mode: Returning current device states without polling")
            return self.devices.copy()
        
        try:
            if not self.client._running:
                _LOGGER.debug("Client not running, connecting...")
                await self.client.async_connect()
            
            # Query state for all devices (for serial/socket only)
            await self._query_all_devices()
            
            # Return current device states
            return self.devices.copy()
            
        except Exception as err:
            _LOGGER.error("Error updating data: %s", err)
            raise UpdateFailed(f"Error updating data: {err}") from err

    async def _query_all_devices(self):
        """Query state for all devices."""
        # Skip for MQTT - devices are updated via messages
        if self.connection_type == CONNECTION_TYPE_MQTT:
            return
        
        _LOGGER.debug("Querying state for %d devices", len(self.devices))
        
        # Send state query commands for each device type
        for device_key, device_info in self.devices.items():
            device_type = device_info["device_type"]
            device_id = device_info["device_id"]
            
            if device_type in RS485_DEVICE:
                device_config = RS485_DEVICE[device_type]
                if "state" in device_config:
                    # Create state query packet
                    state_config = device_config["state"]
                    packet = bytearray([
                        0xF7,
                        state_config["id"],
                        device_id,
                        state_config["cmd"],
                        0x00, 0x00, 0x00, 0x00
                    ])
                    
                    # Calculate checksum
                    checksum = 0
                    for b in packet[:-2]:
                        checksum ^= b
                    add = sum(packet[:-2]) & 0xFF
                    packet[-2] = checksum
                    packet[-1] = add
                    
                    # Send query
                    await self.hass.async_add_executor_job(
                        self.client._conn.send, bytes(packet)
                    )
                    
                    # Small delay between queries
                    await asyncio.sleep(0.05)

    async def async_config_entry_first_refresh(self) -> None:
        """Perform first refresh."""
        _LOGGER.info("Performing first refresh")
        await self.client.async_connect()
        
        # For non-MQTT connections, do initial polling
        if self.connection_type != CONNECTION_TYPE_MQTT:
            await super().async_config_entry_first_refresh()
        else:
            # For MQTT, just set initial data
            self.data = self.devices.copy()
            _LOGGER.debug("MQTT mode: Initial data set with %d devices", len(self.devices))

    async def async_shutdown(self):
        """Shutdown the coordinator."""
        _LOGGER.info("Shutting down coordinator")
        await self.hass.async_add_executor_job(self.client.close)

    @callback
    def _device_update_callback(self, device_type: str, device_id: int, state: Dict[str, Any]):
        """Handle device state updates."""
        # Skip if device type not in enabled capabilities
        if device_type not in self.capabilities:
            return
            
        device_key = f"{device_type}_{device_id}"
        
        # Update or create device entry
        if device_key not in self.devices:
            _LOGGER.info("New device detected via state update: %s", device_key)
            self.devices[device_key] = {
                "device_type": device_type,
                "device_id": device_id,
                "name": f"{device_type.title()} {device_id}",
                "state": state
            }
            # Check if platform needs to be loaded
            self._check_and_load_platform(device_type)
        else:
            self.devices[device_key]["state"] = state
        
        _LOGGER.debug("Device %s updated with state: %s", device_key, state)
        
        # Trigger coordinator update
        self.async_set_updated_data(self.devices)
        
        # Call entity callbacks if registered
        if device_key in self._entity_callbacks:
            for callback in self._entity_callbacks[device_key]:
                callback()

    def register_entity_callback(self, device_key: str, callback: Callable):
        """Register a callback for entity updates."""
        if device_key not in self._entity_callbacks:
            self._entity_callbacks[device_key] = []
        self._entity_callbacks[device_key].append(callback)
        _LOGGER.debug("Registered entity callback for %s", device_key)

    def unregister_entity_callback(self, device_key: str, callback: Callable):
        """Unregister a callback for entity updates."""
        if device_key in self._entity_callbacks:
            try:
                self._entity_callbacks[device_key].remove(callback)
                _LOGGER.debug("Unregistered entity callback for %s", device_key)
            except ValueError:
                pass

    async def send_command(self, device_type: str, device_id: int, command: str, payload: Any):
        """Send a command to a device."""
        _LOGGER.debug("Sending command %s to %s_%d with payload %s", 
                     command, device_type, device_id, payload)
        await self.hass.async_add_executor_job(
            self.client.send_command,
            device_type,
            command,
            str(device_id),
            payload
        )

    def get_device_info(self, device_key: str) -> dict:
        """Get device info for Home Assistant."""
        device = self.devices.get(device_key, {})
        return {
            "identifiers": {(DOMAIN, device_key)},
            "name": device.get("name", device_key),
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "configuration_url": DOCUMENTATION_URL,
        }
    
    def get_platforms_to_load(self) -> set:
        """Get platforms that need to be loaded."""
        return self._platforms_to_load