"""Sensor platform for Ezville Wallpad."""
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower, UnitOfEnergy, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, log_debug, log_info, log_warning, log_error, MANUFACTURER, MODEL, DOCUMENTATION_URL
from .coordinator import EzvilleWallpadCoordinator

_LOGGER = logging.getLogger("custom_components.ezville_wallpad.sensor")


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ezville Wallpad sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    _LOGGER.info("Setting up sensor platform")
    
    # Track added entities
    added_devices = set()
    
    @callback
    def async_add_sensors(device_key: str, device_info: dict):
        """Add new sensor entities."""
        entities = []
        device_type = device_info.get("device_type")
        
        log_debug(_LOGGER, device_type, "async_add_sensors called for device_key=%s, device_type=%s", device_key, device_type)
        
        # Add energy monitor sensors
        if device_type == "energy" and not device_info.get("is_cmd_sensor", False):
            if f"{device_key}_meter" not in added_devices:
                added_devices.add(f"{device_key}_meter")
                entities.append(EzvilleEnergyMeterSensor(coordinator, device_key, device_info))
                log_info(_LOGGER, device_type, "Added energy meter sensor for %s", device_key)
            if f"{device_key}_power" not in added_devices:
                added_devices.add(f"{device_key}_power")
                entities.append(EzvilleEnergyPowerSensor(coordinator, device_key, device_info))
                log_info(_LOGGER, device_type, "Added energy power sensor for %s", device_key)
        
        # Add plug power sensor
        if device_type == "plug" and not device_info.get("is_cmd_sensor", False):
            if f"{device_key}_power" not in added_devices:
                added_devices.add(f"{device_key}_power")
                entities.append(EzvillePowerSensor(coordinator, device_key, device_info))
                log_info(_LOGGER, device_type, "Added power sensor for %s", device_key)
        
        # Add thermostat temperature sensors
        if device_type == "thermostat" and not device_info.get("is_cmd_sensor", False):
            if f"{device_key}_current_temp" not in added_devices:
                added_devices.add(f"{device_key}_current_temp")
                entities.append(EzvilleThermostatCurrentSensor(coordinator, device_key, device_info))
                log_info(_LOGGER, device_type, "Added thermostat current temperature sensor for %s", device_key)
            if f"{device_key}_target_temp" not in added_devices:
                added_devices.add(f"{device_key}_target_temp")
                entities.append(EzvilleThermostatTargetSensor(coordinator, device_key, device_info))
                log_info(_LOGGER, device_type, "Added thermostat target temperature sensor for %s", device_key)
        
        # Add elevator calling sensor
        if device_type == "elevator" and not device_info.get("is_cmd_sensor", False):
            if f"{device_key}_calling" not in added_devices:
                added_devices.add(f"{device_key}_calling")
                entities.append(EzvilleElevatorCallingSensor(coordinator, device_key, device_info))
                log_info(_LOGGER, device_type, "Added elevator calling sensor for %s", device_key)
        
        # Add unknown device sensor
        if device_type == "unknown":
            if f"{device_key}_state" not in added_devices:
                added_devices.add(f"{device_key}_state")
                entities.append(EzvilleUnknownSensor(coordinator, device_key, device_info))
                log_info(_LOGGER, device_type, "Added unknown device sensor for %s with device_info: %s", device_key, device_info)
            else:
                log_debug(_LOGGER, device_type, "Unknown device sensor %s already added", device_key)
        
        # Add CMD sensor - check by is_cmd_sensor flag
        if device_info.get("is_cmd_sensor", False):
            if f"{device_key}_state" not in added_devices:
                added_devices.add(f"{device_key}_state")
                entities.append(EzvilleCmdSensor(coordinator, device_key, device_info))
                log_info(_LOGGER, device_type, "Added CMD sensor for %s with device_info: %s", device_key, device_info)
            #else:
            #    log_debug(_LOGGER, device_type, "CMD sensor %s already added", device_key)
        
        if entities:
            async_add_entities(entities)
            log_debug(_LOGGER, device_type, "Adding %d entities for device_key=%s", len(entities), device_key)
        else:
            log_debug(_LOGGER, device_type, "No entities to add for device_key=%s", device_key)
    
    # Add existing devices
    _LOGGER.info("Adding existing devices to sensor platform")
    for device_key, device_info in coordinator.devices.items():
        device_type = device_info["device_type"]
        log_debug(_LOGGER, device_type, "Checking device %s with type %s", device_key, device_info.get("device_type"))
        # Check for sensors: regular device types or CMD sensors
        if device_type in ["plug", "energy", "thermostat", "elevator", "unknown"] or device_info.get("is_cmd_sensor", False):
            async_add_sensors(device_key, device_info)
    
    # Register callback for new devices
    @callback
    def device_added():
        """Handle new device added."""
        _LOGGER.debug("Device added callback triggered")
        # Create a copy of the devices to avoid dictionary changed size during iteration
        devices_copy = dict(coordinator.devices)
        for device_key, device_info in devices_copy.items():
            device_type = device_info["device_type"]
            # Check for sensors: regular device types or CMD sensors
            if device_type in ["plug", "energy", "thermostat", "elevator", "unknown"] or device_info.get("is_cmd_sensor", False):
                async_add_sensors(device_key, device_info)
    
    # Listen for coordinator updates
    coordinator.async_add_listener(device_added)
    
    _LOGGER.info("Sensor platform setup complete with %d entities", len(added_devices))


class EzvillePowerSensor(CoordinatorEntity, SensorEntity):
    """Ezville Wallpad power sensor for smart plugs."""

    def __init__(
        self,
        coordinator: EzvilleWallpadCoordinator,
        device_key: str,
        device_info: dict,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_key = device_key
        self._device_info = device_info
        self._attr_unique_id = f"{DOMAIN}_{device_key}_power"
        # Extract room and plug number for naming
        if "_" in device_key:
            parts = device_key.split("_")
            if len(parts) >= 3:
                room_num = parts[1]
                plug_num = parts[2]
                self._attr_name = f"Plug {room_num} {plug_num} Power"
            else:
                self._attr_name = f"{device_info.get('name', 'Plug')} Power"
        else:
            self._attr_name = f"{device_info.get('name', 'Plug')} Power"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        
        # Device info - use room-based grouping
        from .device import EzvilleWallpadDevice
        base_device = EzvilleWallpadDevice(coordinator, device_key, self._attr_unique_id, self._attr_name)
        self._attr_device_info = base_device.device_info
        
        # Initialize state tracking
        self._last_state = None
        
        log_debug(_LOGGER, "plug", "Initialized power sensor: %s", self._attr_name)

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        device = self.coordinator.devices.get(self._device_key, {})
        state = device.get("state", {})
        return state.get("power_usage", 0)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._device_key in self.coordinator.devices

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Get current state
        device = self.coordinator.devices.get(self._device_key, {})
        current_state = device.get("state", {})
        
        # Check if state actually changed
        if self._last_state == current_state:
            # No change, skip update
            return
        
        # State changed, update last state
        self._last_state = current_state.copy()
        
        # Schedule update safely from any thread
        if hasattr(self, 'hass') and self.hass:
            self.hass.loop.call_soon_threadsafe(lambda: self.schedule_update_ha_state(True))
        else:
            device_type = self._device_info.get("device_type", "")
            log_debug(_LOGGER, device_type, "===> Cannot update state for %s - hass not available", self._attr_name)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Register for direct updates
        self.coordinator.register_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
        log_debug(_LOGGER, "plug", "Power sensor %s added to hass", self._attr_name)

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        # Unregister callback
        self.coordinator.unregister_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
        log_debug(_LOGGER, "plug", "Power sensor %s removed from hass", self._attr_name)


class EzvilleEnergyMeterSensor(CoordinatorEntity, SensorEntity):
    """Ezville Wallpad energy meter sensor."""

    def __init__(
        self,
        coordinator: EzvilleWallpadCoordinator,
        device_key: str,
        device_info: dict,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_key = device_key
        self._device_info = device_info
        self._attr_unique_id = f"{DOMAIN}_{device_key}_meter"
        self._attr_name = f"{device_info.get('name', 'Energy')} Meter"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        
        # Device info
        from .device import EzvilleWallpadDevice
        base_device = EzvilleWallpadDevice(coordinator, device_key, self._attr_unique_id, self._attr_name)
        self._attr_device_info = base_device.device_info
        
        # Initialize state tracking
        self._last_state = None
        
        log_debug(_LOGGER, "energy", "Initialized energy meter sensor: %s", self._attr_name)

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        device = self.coordinator.devices.get(self._device_key, {})
        state = device.get("state", {})
        # Convert from units to kWh
        return state.get("usage", 0)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._device_key in self.coordinator.devices

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Get current state
        device = self.coordinator.devices.get(self._device_key, {})
        current_state = device.get("state", {})
        
        # Check if state actually changed
        if self._last_state == current_state:
            # No change, skip update
            return
        
        # State changed, update last state
        self._last_state = current_state.copy()
        
        # Schedule update safely from any thread
        if hasattr(self, 'hass') and self.hass:
            self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)
        else:
            log_debug(_LOGGER, "energy", "===> Cannot update state for %s - hass not available", self._attr_name)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Register for direct updates
        self.coordinator.register_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
        log_debug(_LOGGER, "energy", "Energy meter sensor %s added to hass", self._attr_name)

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        # Unregister callback
        self.coordinator.unregister_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
        log_debug(_LOGGER, "energy", "Energy meter sensor %s removed from hass", self._attr_name)


class EzvilleEnergyPowerSensor(CoordinatorEntity, SensorEntity):
    """Ezville Wallpad energy power sensor."""

    def __init__(
        self,
        coordinator: EzvilleWallpadCoordinator,
        device_key: str,
        device_info: dict,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_key = device_key
        self._device_info = device_info
        self._attr_unique_id = f"{DOMAIN}_{device_key}_power"
        self._attr_name = f"{device_info.get('name', 'Energy')} Power"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        
        # Device info
        from .device import EzvilleWallpadDevice
        base_device = EzvilleWallpadDevice(coordinator, device_key, self._attr_unique_id, self._attr_name)
        self._attr_device_info = base_device.device_info
        
        # Initialize state tracking
        self._last_state = None
        
        log_debug(_LOGGER, "energy", "Initialized energy power sensor: %s", self._attr_name)

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        device = self.coordinator.devices.get(self._device_key, {})
        state = device.get("state", {})
        # Convert from units to watts
        return state.get("power", 0)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._device_key in self.coordinator.devices

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Get current state
        device = self.coordinator.devices.get(self._device_key, {})
        current_state = device.get("state", {})
        
        # Check if state actually changed
        if self._last_state == current_state:
            # No change, skip update
            return
        
        # State changed, update last state
        self._last_state = current_state.copy()
        
        # Schedule update safely from any thread
        if hasattr(self, 'hass') and self.hass:
            self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)
        else:
            log_debug(_LOGGER, "energy", "===> Cannot update state for %s - hass not available", self._attr_name)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Register for direct updates
        self.coordinator.register_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
        log_debug(_LOGGER, "energy", "Energy power sensor %s added to hass", self._attr_name)

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        # Unregister callback
        self.coordinator.unregister_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
        log_debug(_LOGGER, "energy", "Energy power sensor %s removed from hass", self._attr_name)


class EzvilleThermostatCurrentSensor(CoordinatorEntity, SensorEntity):
    """Ezville Wallpad thermostat current temperature sensor."""

    def __init__(
        self,
        coordinator: EzvilleWallpadCoordinator,
        device_key: str,
        device_info: dict,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_key = device_key
        self._device_info = device_info
        self._attr_unique_id = f"{DOMAIN}_{device_key}_current_temperature"
        self._attr_name = f"{device_info.get('name', 'Thermostat')} Current Temperature"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        
        # Device info
        from .device import EzvilleWallpadDevice
        base_device = EzvilleWallpadDevice(coordinator, device_key, self._attr_unique_id, self._attr_name)
        self._attr_device_info = base_device.device_info
        
        # Initialize state tracking
        self._last_state = None
        
        log_debug(_LOGGER, "thermostat", "Initialized thermostat current temperature sensor: %s", self._attr_name)

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        device = self.coordinator.devices.get(self._device_key, {})
        state = device.get("state", {})
        return state.get("current_temperature", None)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._device_key in self.coordinator.devices

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Get current state
        device = self.coordinator.devices.get(self._device_key, {})
        current_state = device.get("state", {})
        
        # Check if state actually changed
        if self._last_state == current_state:
            # No change, skip update
            return
        
        # State changed, update last state
        self._last_state = current_state.copy()
        
        # Schedule update safely from any thread
        if hasattr(self, 'hass') and self.hass:
            self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)
        else:
            log_debug(_LOGGER, "thermostat", "===> Cannot update state for %s - hass not available", self._attr_name)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Register for direct updates
        self.coordinator.register_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
        log_debug(_LOGGER, "thermostat", "Thermostat current temperature sensor %s added to hass", self._attr_name)

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        # Unregister callback
        self.coordinator.unregister_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
        log_debug(_LOGGER, "thermostat", "Thermostat current temperature sensor %s removed from hass", self._attr_name)


class EzvilleThermostatTargetSensor(CoordinatorEntity, SensorEntity):
    """Ezville Wallpad thermostat target temperature sensor."""

    def __init__(
        self,
        coordinator: EzvilleWallpadCoordinator,
        device_key: str,
        device_info: dict,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_key = device_key
        self._device_info = device_info
        self._attr_unique_id = f"{DOMAIN}_{device_key}_target_temperature"
        self._attr_name = f"{device_info.get('name', 'Thermostat')} Target Temperature"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        
        # Device info
        from .device import EzvilleWallpadDevice
        base_device = EzvilleWallpadDevice(coordinator, device_key, self._attr_unique_id, self._attr_name)
        self._attr_device_info = base_device.device_info
        
        # Initialize state tracking
        self._last_state = None
        
        log_debug(_LOGGER, "thermostat", "Initialized thermostat target temperature sensor: %s", self._attr_name)

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        device = self.coordinator.devices.get(self._device_key, {})
        state = device.get("state", {})
        return state.get("target_temperature", None)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._device_key in self.coordinator.devices

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Get current state
        device = self.coordinator.devices.get(self._device_key, {})
        current_state = device.get("state", {})
        
        # Check if state actually changed
        if self._last_state == current_state:
            # No change, skip update
            return
        
        # State changed, update last state
        self._last_state = current_state.copy()
        
        # Schedule update safely from any thread
        if hasattr(self, 'hass') and self.hass:
            self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)
        else:
            log_debug(_LOGGER, "thermostat", "===> Cannot update state for %s - hass not available", self._attr_name)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Register for direct updates
        self.coordinator.register_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
        log_debug(_LOGGER, "thermostat", "Thermostat target temperature sensor %s added to hass", self._attr_name)

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        # Unregister callback
        self.coordinator.unregister_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
        log_debug(_LOGGER, "thermostat", "Thermostat target temperature sensor %s removed from hass", self._attr_name)


class EzvilleCmdSensor(CoordinatorEntity, SensorEntity):
    """Ezville CMD Sensor for non-state packets."""

    def __init__(self, coordinator: EzvilleWallpadCoordinator, device_key: str, device_info: dict):
        """Initialize the sensor."""
        super().__init__(coordinator)
        
        self._device_key = device_key
        self._device_info = device_info
        base_device_type = device_info.get("device_type", "")
        base_device_key = device_info.get("base_device_key", "")
        
        # Entity attributes
        self._attr_unique_id = f"{DOMAIN}_{device_key}_state"
        self._attr_name = device_info.get("name", "Unknown CMD")
        self._attr_icon = "mdi:console-network"
        
        # Device info - group with base device
        from .device import EzvilleWallpadDevice
        if base_device_key:
            # Get device info from the base device for grouping
            base_device_for_group = EzvilleWallpadDevice(coordinator, base_device_key, "", "")
            self._attr_device_info = base_device_for_group.device_info
        else:
            # Fallback
            base_device = EzvilleWallpadDevice(coordinator, device_key, self._attr_unique_id, self._attr_name)
            self._attr_device_info = base_device.device_info
        
        # Initialize state tracking
        self._last_seen = None
        self._packet_data = {}
        
        # Log with proper device type
        log_debug(_LOGGER, base_device_type, "Initialized CMD sensor: %s (device_type: %s, base_key: %s)", 
                  self._attr_name, base_device_type, base_device_key)

    @property
    def native_value(self) -> Optional[str]:
        """Return the state of the sensor."""
        # Return the packet data
        if self._packet_data:
            return self._packet_data.get("data", "No data")
        return "No data"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attributes = {
            "device_id": self._packet_data.get("device_id", "Unknown"),
            "device_num": self._packet_data.get("device_num", "0x00"),
            "command": self._packet_data.get("command", "Unknown"),
            "raw_data": self._packet_data.get("raw_data", "No data"),
            "packet_length": self._packet_data.get("packet_length", 0),
            "full_data": self._packet_data.get("data", "No data"),
            "last_seen": self._last_seen
        }
        
        return attributes

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # CMD sensors are always available once created
        return True

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Check if device still exists in coordinator
        if self._device_key in self.coordinator.devices:
            device = self.coordinator.devices.get(self._device_key, {})
            state = device.get("state", {})
            
            # Get last_seen from state
            state_last_seen = state.get("last_seen")
            if state_last_seen:
                # Check if the update is within 1 second
                from datetime import datetime, timedelta
                try:
                    last_seen_time = datetime.fromisoformat(state_last_seen)
                    current_time = datetime.now()
                    time_diff = current_time - last_seen_time
                    
                    # Only update if within 1 second
                    if time_diff <= timedelta(seconds=1):
                        # Update our internal state
                        self._last_seen = state_last_seen
                        self._packet_data = state
                        
                        # Schedule update
                        if hasattr(self, 'hass') and self.hass:
                            self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)
                            
                        base_device_type = self._device_info.get("device_type", "")
                        log_info(_LOGGER, base_device_type, "CMD sensor %s received packet at %s", self._attr_name, self._last_seen)
                    else:
                        base_device_type = self._device_info.get("device_type", "")
                        log_debug(_LOGGER, base_device_type, "CMD sensor %s skipped old update (%.1f seconds old)", 
                                 self._attr_name, time_diff.total_seconds())
                except Exception as e:
                    base_device_type = self._device_info.get("device_type", "")
                    log_error(_LOGGER, base_device_type, "Error processing last_seen time: %s", e)
            else:
                # No last_seen in state, update anyway (for compatibility)
                self._last_seen = datetime.now().isoformat()
                self._packet_data = state
                
                # Schedule update
                if hasattr(self, 'hass') and self.hass:
                    self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)
                    
                base_device_type = self._device_info.get("device_type", "")
                log_info(_LOGGER, base_device_type, "CMD sensor %s received packet (no last_seen)", self._attr_name)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        
        # Register for coordinator updates
        self.coordinator.register_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
        
        base_device_type = self._device_info.get("device_type", "")
        log_debug(_LOGGER, base_device_type, "CMD sensor %s added to hass", self._attr_name)

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        
        # Unregister callback
        self.coordinator.unregister_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
        
        base_device_type = self._device_info.get("device_type", "")
        log_debug(_LOGGER, base_device_type, "CMD sensor %s removed from hass", self._attr_name)


class EzvilleUnknownSensor(CoordinatorEntity, SensorEntity):
    """Ezville Unknown Device Sensor."""

    def __init__(self, coordinator: EzvilleWallpadCoordinator, device_key: str, device_info: dict):
        """Initialize the sensor."""
        super().__init__(coordinator)
        
        self._device_key = device_key
        self._device_info = device_info
        device_id = device_info.get("device_id", "")
        
        # Entity attributes
        self._attr_unique_id = f"{DOMAIN}_{device_key}_state"
        # Create entity name with signature (8 hex chars)
        if device_id:
            # device_id is the signature (8 hex chars)
            self._attr_name = f"Unknown {device_id}"
        else:
            self._attr_name = "Unknown"
        self._attr_icon = "mdi:help-circle"
        
        # Device info - use unknown device grouping
        from .device import EzvilleWallpadDevice
        base_device = EzvilleWallpadDevice(coordinator, device_key, self._attr_unique_id, self._attr_name)
        self._attr_device_info = base_device.device_info
        
        # Initialize state tracking
        self._last_state = None
        
        log_debug(_LOGGER, "unknown", "Initialized unknown device sensor: %s (device_id: %s)", self._attr_name, device_id)

    @property
    def native_value(self) -> Optional[str]:
        """Return the state of the sensor."""
        device = self.coordinator.devices.get(self._device_key, {})
        state = device.get("state", {})
        # Return the raw data as string
        return state.get("data", "No data")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        device = self.coordinator.devices.get(self._device_key, {})
        state = device.get("state", {})
        
        attributes = {
            "device_id": state.get("device_id", "Unknown"),
            "device_num": state.get("device_num", "0x00"),
            "command": state.get("command", "Unknown"),
            "raw_data": state.get("raw_data", "No data"),
            "signature": state.get("signature", "Unknown")
        }
        
        return attributes

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._device_key in self.coordinator.devices

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Get current state
        device = self.coordinator.devices.get(self._device_key, {})
        current_state = device.get("state", {})
        
        # Check if state actually changed - compare only data field for unknown sensors
        if self._last_state is not None and self._last_state.get("data") == current_state.get("data"):
            # No change, skip update
            return
        
        # State changed, update last state
        self._last_state = current_state.copy()
        
        # Schedule update safely from any thread
        if hasattr(self, 'hass') and self.hass:
            self.hass.loop.call_soon_threadsafe(lambda: self.schedule_update_ha_state(True))
        else:
            log_debug(_LOGGER, "unknown", "===> Cannot update state for %s - hass not available", self._attr_name)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Register for direct updates
        self.coordinator.register_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
        log_debug(_LOGGER, "unknown", "Unknown device sensor %s added to hass", self._attr_name)

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        # Unregister callback
        self.coordinator.unregister_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
        log_debug(_LOGGER, "unknown", "Unknown device sensor %s removed from hass", self._attr_name)


class EzvilleElevatorCallingSensor(CoordinatorEntity, SensorEntity):
    """Ezville Wallpad elevator calling sensor."""

    def __init__(
        self,
        coordinator: EzvilleWallpadCoordinator,
        device_key: str,
        device_info: dict,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_key = device_key
        self._device_info = device_info
        self._attr_unique_id = f"{DOMAIN}_{device_key}_calling"
        self._attr_name = "Elevator Calling"
        self._attr_icon = "mdi:elevator"
        
        # Device info
        from .device import EzvilleWallpadDevice
        base_device = EzvilleWallpadDevice(coordinator, device_key, self._attr_unique_id, self._attr_name)
        self._attr_device_info = base_device.device_info
        
        # Initialize state tracking
        self._last_state = None
        
        log_debug(_LOGGER, "elevator", "Initialized elevator calling sensor: %s", self._attr_name)

    @property
    def native_value(self) -> Optional[str]:
        """Return the state of the sensor."""
        device = self.coordinator.devices.get(self._device_key, {})
        state = device.get("state", {})
        status = state.get("status", 0)
        
        # Determine status based on the value
        if status == 0x0:
            return "off"
        elif status == 0x2:
            return "on"
        elif status == 0x4:
            return "cut"
        else:
            return str(status)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        device = self.coordinator.devices.get(self._device_key, {})
        state = device.get("state", {})
        device_info = device.get("device_info", {})
        
        # Get the raw packet data if available
        raw_data = "No data"
        if "raw_packet" in state:
            raw_data = state["raw_packet"].hex() if isinstance(state["raw_packet"], bytes) else state["raw_packet"]
        elif "data" in state:
            raw_data = state["data"]
        
        attributes = {
            "device_id": state.get("device_id", device_info.get("device_id", "Unknown")),
            "device_num": state.get("device_num", device_info.get("device_num", "0x00")),
            "raw_data": raw_data,
            "floor": state.get("floor", 0)
        }
        
        return attributes

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._device_key in self.coordinator.devices

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Get current state
        device = self.coordinator.devices.get(self._device_key, {})
        current_state = device.get("state", {})
        
        # Check if state actually changed
        if self._last_state == current_state:
            # No change, skip update
            return
        
        # State changed, update last state
        self._last_state = current_state.copy()
        
        # Schedule update safely from any thread
        if hasattr(self, 'hass') and self.hass:
            self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)
        else:
            log_debug(_LOGGER, "elevator", "===> Cannot update state for %s - hass not available", self._attr_name)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Register for direct updates
        self.coordinator.register_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
        log_debug(_LOGGER, "elevator", "Elevator calling sensor %s added to hass", self._attr_name)

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        # Unregister callback
        self.coordinator.unregister_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
        log_debug(_LOGGER, "elevator", "Elevator calling sensor %s removed from hass", self._attr_name)
