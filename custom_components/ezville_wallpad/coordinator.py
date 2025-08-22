"""Data update coordinator for Ezville Wallpad."""
import logging
import asyncio
import threading
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
    DOCUMENTATION_URL,
    log_debug,
    log_info,
    log_warning,
    log_error,
    log_system,
)
from .rs485_client import EzvilleRS485Client

_LOGGER = logging.getLogger("custom_components.ezville_wallpad.coordinator")


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
        # Always include all capabilities for device discovery
        self.capabilities = [
            "light", "plug", "thermostat", "fan", "gas", 
            "energy", "elevator", "doorbell"
        ]
        
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
        
        # Always register callback for unknown devices
        self.client.register_callback("unknown", self._device_update_callback)
        _LOGGER.debug("Registered callback for unknown devices")
        
        # Unknown devices will be created dynamically when discovered
        
        # Don't create default unknown device - let it be created dynamically
        _LOGGER.debug("Unknown devices will be created dynamically when discovered")

    def _initialize_default_devices(self):
        """Initialize default devices for enabled capabilities."""
        _LOGGER.info("Initializing default devices for initial setup")
        
        # Create initial devices according to requirements
        if "doorbell" in self.capabilities:
            device_key = "doorbell"
            self.devices[device_key] = {
                "device_type": "doorbell",
                "device_id": None,
                "name": "Doorbell",
                "state": {"ring": False}
            }
            _LOGGER.debug("Created default doorbell: %s", device_key)
        
        if "elevator" in self.capabilities:
            device_key = "elevator"
            self.devices[device_key] = {
                "device_type": "elevator",
                "device_id": None,
                "name": "Elevator",
                "state": {"status": 0, "floor": 1}
            }
            _LOGGER.debug("Created default elevator: %s", device_key)
        
        if "energy" in self.capabilities:
            device_key = "energy"
            self.devices[device_key] = {
                "device_type": "energy",
                "device_id": None,
                "name": "Energy",
                "state": {"power": 0, "usage": 0}
            }
            _LOGGER.debug("Created default energy meter: %s", device_key)
        
        if "gas" in self.capabilities:
            device_key = "gas"
            self.devices[device_key] = {
                "device_type": "gas",
                "device_id": None,
                "name": "Gas",
                "state": {"closed": True}
            }
            _LOGGER.debug("Created default gas valve: %s", device_key)
        
        if "fan" in self.capabilities:
            device_key = "fan"
            self.devices[device_key] = {
                "device_type": "fan",
                "device_id": None,
                "name": "Ventilation",
                "state": {"power": False, "speed": 0, "mode": "bypass"}
            }
            _LOGGER.debug("Created default ventilation fan: %s", device_key)
        
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
            
            _LOGGER.info("Created %d default devices", len(self.devices))
        
        # Determine which platforms need to be loaded
        self._determine_platforms_to_load()
        
        # Climate platform needs to load thermostat temperature sensors
        if "thermostat" in self.capabilities:
            # Force sensor platform loading for thermostat temperature sensors
            from homeassistant.const import Platform
            self._platforms_to_load.add(Platform.SENSOR)

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

    def _on_device_discovered(self, device_type: str, device_id: Any):
        """Handle new device discovery."""
        # Always log unknown device discovery
        if device_type == "unknown":
            _LOGGER.info("Unknown device discovery triggered: device_type=%s, device_id=%s", device_type, device_id)
        
        # Unknown devices should always be processed
        if device_type != "unknown" and device_type not in self.capabilities:
            _LOGGER.debug("Ignoring discovered device %s_%s (not in capabilities)", 
                         device_type, device_id)
            return
        
        # Handle different key formats based on device type
        if device_type in ["light", "plug", "thermostat"]:
            # Multi-instance devices with room/num or room only
            device_key = f"{device_type}_{device_id}" if device_id else device_type
        elif device_type == "unknown":
            # Unknown devices use signature as key
            device_key = f"unknown_{device_id}"
        else:
            # Single instance devices (fan, gas, energy, elevator, doorbell)
            device_key = device_type
        
        if device_key not in self.devices:
            _LOGGER.info("Discovered new device: %s (type: %s, id: %s)", device_key, device_type, device_id)
            
            # Parse device ID to get display name
            if device_type in ["light", "plug"] and isinstance(device_id, str) and "_" in device_id:
                # For light_1_2 format
                parts = device_id.split("_")
                display_name = f"{device_type.title()} {parts[0]} {parts[1]}"
            elif device_type == "thermostat" and device_id:
                display_name = f"{device_type.title()} {device_id}"
            elif device_type == "unknown":
                # device_id is the signature (8 hex characters)
                display_name = f"Unknown {device_id.upper()}"
            else:
                # Single instance devices
                display_name = device_type.title()
            
            # Create device entry
            self.devices[device_key] = {
                "device_type": device_type,
                "device_id": device_id,
                "name": display_name,
                "state": {}
            }
            
            _LOGGER.info("Created device entry: key=%s, device=%s", device_key, self.devices[device_key])
            _LOGGER.info("Total devices after addition: %d", len(self.devices))
            
            # Check if platform needs to be loaded
            self._check_and_load_platform(device_type)
            
            # Notify that data has been updated - schedule in event loop
            self.hass.loop.call_soon_threadsafe(
                lambda: self.async_set_updated_data(self.devices)
            )
            
            # For unknown devices, also trigger sensor platform loading if not loaded
            if device_type == "unknown":
                from homeassistant.const import Platform
                if Platform.SENSOR not in self._platform_loaded:
                    _LOGGER.info("Loading sensor platform for unknown device")
                    self._platform_loaded.add(Platform.SENSOR)
                    self.hass.async_create_task(
                        self.hass.config_entries.async_forward_entry_setup(
                            self.config_entry, Platform.SENSOR
                        )
                    )
                else:
                    # Sensor platform already loaded, manually trigger device_added callback
                    _LOGGER.info("Sensor platform already loaded, triggering manual update")
                    # Force update of coordinator data
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
        elif device_type == "thermostat":
            if Platform.CLIMATE not in self._platform_loaded:
                platforms_needed.add(Platform.CLIMATE)
            # Also load sensor platform for temperature sensors
            if Platform.SENSOR not in self._platform_loaded:
                platforms_needed.add(Platform.SENSOR)
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
        elif device_type == "unknown" and Platform.SENSOR not in self._platform_loaded:
            # Use sensor platform for unknown devices
            platforms_needed.add(Platform.SENSOR)
        
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
    def _device_update_callback(self, device_type: str, device_id: Any, state: Dict[str, Any]):
        """Handle device state updates."""
        # Always log unknown devices
        if device_type == "unknown":
            _LOGGER.info("==> Unknown device callback: device_type=%s, device_id=%s, state=%s",
                         device_type, device_id, state)
        
        # Get logging enabled device types from options
        log_device_types = self.options.get("logging_device_types", [])
        
        # Check if this device type should be logged
        should_log = device_type in log_device_types or "unknown" in log_device_types
        if should_log:
            log_debug(_LOGGER, device_type, "==> Coordinator received callback: device_type=%s, device_id=%s, state=%s",
                         device_type, device_id, state)
        
        # Skip if device type not in enabled capabilities (except unknown)
        if device_type != "unknown" and device_type not in self.capabilities:
            if should_log:
                log_debug(_LOGGER, device_type, "==> Skipping device_type %s (not in capabilities)", device_type)
            return
            
        # Handle different key formats based on device type
        if device_type in ["light", "plug", "thermostat"]:
            # Multi-instance devices with room/num or room only
            device_key = f"{device_type}_{device_id}" if device_id else device_type
        elif device_type == "unknown":
            # Unknown devices use signature as key
            device_key = f"unknown_{device_id}"
        else:
            # Single instance devices (fan, gas, energy, elevator, doorbell)
            device_key = device_type
        
        # Check if state has actually changed
        is_new_device = device_key not in self.devices
        state_changed = False
        
        if not is_new_device:
            # Compare old and new state
            old_state = self.devices[device_key].get("state", {})
            state_changed = old_state != state
            
            if not state_changed:
                # No change, skip update
                if should_log:
                    log_debug(_LOGGER, device_type, "==> Device %s state unchanged, skipping update", device_key)
                return
        
        # Update or create device entry
        if is_new_device:
            log_info(_LOGGER, device_type, "==> New device detected via state update: %s", device_key)
            
            # Parse device ID to get display name
            if device_type in ["light", "plug"] and isinstance(device_id, str) and "_" in device_id:
                # For light_1_2 format
                parts = device_id.split("_")
                display_name = f"{device_type.title()} {parts[0]} {parts[1]}"
            elif device_type == "thermostat" and device_id:
                display_name = f"{device_type.title()} {device_id}"
            elif device_type == "unknown":
                # device_id is the signature (8 hex characters)  
                display_name = f"Unknown {device_id.upper()}"
            else:
                # Single instance devices
                display_name = device_type.title()
            
            self.devices[device_key] = {
                "device_type": device_type,
                "device_id": device_id,
                "name": display_name,
                "state": state
            }
            # Check if platform needs to be loaded
            self._check_and_load_platform(device_type)
        else:
            old_device_state = self.devices[device_key].get("state", {}).copy()
            self.devices[device_key]["state"] = state
            if should_log:
                log_debug(_LOGGER, device_type, "==> Device %s state updated from %s to %s", device_key, old_device_state, state)
        
        if should_log:
            log_debug(_LOGGER, device_type, "==> Device %s current full info: %s", device_key, self.devices.get(device_key))
        
        # Trigger coordinator update - schedule in event loop if called from thread
        if threading.current_thread() is threading.main_thread():
            self.async_set_updated_data(self.devices)
        else:
            self.hass.loop.call_soon_threadsafe(
                lambda: self.async_set_updated_data(self.devices)
            )
        
        # Call entity callbacks if registered (only if state changed or new device)
        if device_key in self._entity_callbacks:
            if should_log:
                log_debug(_LOGGER, device_type, "==> Found %d entity callbacks for device_key %s", 
                             len(self._entity_callbacks[device_key]), device_key)
            for idx, callback in enumerate(self._entity_callbacks[device_key]):
                # Call callbacks safely from any thread
                try:
                    if should_log:
                        log_debug(_LOGGER, device_type, "==> Calling entity callback [%d] for %s", idx, device_key)
                    callback()
                    if should_log:
                        log_debug(_LOGGER, device_type, "==> Entity callback [%d] completed for %s", idx, device_key)
                except Exception as err:
                    log_error(_LOGGER, device_type, "==> Error in entity callback [%d] for %s: %s", idx, device_key, err)
        else:
            if should_log:
                log_debug(_LOGGER, device_type, "==> No entity callbacks registered for device_key %s", device_key)

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

    async def send_command(self, device_type: str, device_id: Any, command: str, payload: Any):
        """Send a command to a device."""
        _LOGGER.debug("Sending command %s to %s_%s with payload %s", 
                     command, device_type, device_id if device_id else "(single)", payload)
        
        # For single devices, device_id might be None
        idn = str(device_id) if device_id is not None else None
        
        await self.hass.async_add_executor_job(
            self.client.send_command,
            device_type,
            command,
            idn,
            payload
        )

    def get_device_info(self, device_key: str) -> dict:
        """Get device info for Home Assistant."""
        # This method is deprecated - use EzvilleWallpadDevice.device_info instead
        from .device import EzvilleWallpadDevice
        base_device = EzvilleWallpadDevice(self, device_key, f"{DOMAIN}_{device_key}", "temp")
        return base_device.device_info
    
    def get_platforms_to_load(self) -> set:
        """Get platforms that need to be loaded."""
        return self._platforms_to_load