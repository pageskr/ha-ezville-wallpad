"""Sensor platform for Ezville Wallpad."""
import logging
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
        
        _LOGGER.debug("async_add_sensors called for device_key=%s, device_type=%s", device_key, device_type)
        
        # Add plug power sensor
        if device_type == "plug" and f"{device_key}_power" not in added_devices:
            added_devices.add(f"{device_key}_power")
            entities.append(EzvillePowerSensor(coordinator, device_key, device_info))
            _LOGGER.info("Added power sensor for %s", device_key)
        
        # Add energy monitor sensors
        if device_type == "energy":
            if f"{device_key}_meter" not in added_devices:
                added_devices.add(f"{device_key}_meter")
                entities.append(EzvilleEnergyMeterSensor(coordinator, device_key, device_info))
                log_info(_LOGGER, "energy", "Added energy meter sensor for %s", device_key)
            if f"{device_key}_power" not in added_devices:
                added_devices.add(f"{device_key}_power")
                entities.append(EzvilleEnergyPowerSensor(coordinator, device_key, device_info))
                log_info(_LOGGER, "energy", "Added energy power sensor for %s", device_key)
        
        # Add thermostat temperature sensors
        if device_type == "thermostat":
            if f"{device_key}_current_temp" not in added_devices:
                added_devices.add(f"{device_key}_current_temp")
                entities.append(EzvilleThermostatCurrentSensor(coordinator, device_key, device_info))
                _LOGGER.info("Added thermostat current temperature sensor for %s", device_key)
            if f"{device_key}_target_temp" not in added_devices:
                added_devices.add(f"{device_key}_target_temp")
                entities.append(EzvilleThermostatTargetSensor(coordinator, device_key, device_info))
                _LOGGER.info("Added thermostat target temperature sensor for %s", device_key)
        
        # Add unknown device sensor
        if device_type == "unknown":
            if f"{device_key}_state" not in added_devices:
                added_devices.add(f"{device_key}_state")
                entities.append(EzvilleUnknownSensor(coordinator, device_key, device_info))
                _LOGGER.info("Added unknown device sensor for %s with device_info: %s", device_key, device_info)
            else:
                _LOGGER.debug("Unknown device sensor %s already added", device_key)
        
        if entities:
            _LOGGER.info("Adding %d entities to Home Assistant", len(entities))
            async_add_entities(entities)
        else:
            _LOGGER.debug("No entities to add for device_key=%s", device_key)
    
    # Add existing devices
    _LOGGER.info("Adding existing devices to sensor platform")
    for device_key, device_info in coordinator.devices.items():
        _LOGGER.debug("Checking device %s with type %s", device_key, device_info.get("device_type"))
        if device_info["device_type"] in ["plug", "energy", "thermostat", "unknown"]:
            async_add_sensors(device_key, device_info)
    
    # Register callback for new devices
    @callback
    def device_added():
        """Handle new device added."""
        _LOGGER.debug("Device added callback triggered")
        # Create a copy of the devices to avoid dictionary changed size during iteration
        devices_copy = dict(coordinator.devices)
        for device_key, device_info in devices_copy.items():
            if device_info["device_type"] in ["plug", "energy", "thermostat", "unknown"]:
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
        
        _LOGGER.debug("Initialized power sensor: %s", self._attr_name)

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
        # Update last detected time
        import time
        self._last_detected = time.time()
        
        # Schedule update safely from any thread
        if hasattr(self, 'hass') and self.hass:
            self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)
        else:
            _LOGGER.debug("===> Cannot update state for %s - hass not available", self._attr_name)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Register for direct updates
        self.coordinator.register_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
        _LOGGER.debug("Power sensor %s added to hass", self._attr_name)

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        # Unregister callback
        self.coordinator.unregister_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
        _LOGGER.debug("Power sensor %s removed from hass", self._attr_name)


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
        self._attr_name = "Energy Meter"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        
        # Device info - use unknown device grouping
        from .device import EzvilleWallpadDevice
        base_device = EzvilleWallpadDevice(coordinator, device_key, self._attr_unique_id, self._attr_name)
        self._attr_device_info = base_device.device_info
        
        _LOGGER.debug("Initialized energy sensor: %s", self._attr_name)

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        device = self.coordinator.devices.get(self._device_key, {})
        state = device.get("state", {})
        # Energy meter already provides kWh value, no conversion needed
        return state.get("usage", 0)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._device_key in self.coordinator.devices

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Update last detected time
        import time
        self._last_detected = time.time()
        
        # Schedule update safely from any thread
        if hasattr(self, 'hass') and self.hass:
            self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)
        else:
            _LOGGER.debug("===> Cannot update state for %s - hass not available", self._attr_name)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Register for direct updates
        self.coordinator.register_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
        _LOGGER.debug("Energy sensor %s added to hass", self._attr_name)

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        # Unregister callback
        self.coordinator.unregister_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
        _LOGGER.debug("Energy sensor %s removed from hass", self._attr_name)


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
        self._attr_name = "Energy Power"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        
        # Device info from coordinator
        self._attr_device_info = coordinator.get_device_info(device_key)
        
        log_debug(_LOGGER, "energy", "Initialized energy power sensor: %s", self._attr_name)

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        device = self.coordinator.devices.get(self._device_key, {})
        state = device.get("state", {})
        return state.get("power", 0)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._device_key in self.coordinator.devices

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Schedule update safely from any thread
        if hasattr(self, 'hass') and self.hass:
            self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)
        else:
            log_debug(_LOGGER, "energy", "Cannot update state for %s - hass not available", self._attr_name)

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
        self._attr_unique_id = f"{DOMAIN}_{device_key}_current_temp"
        
        # Extract room number for naming
        parts = device_key.split("_")
        if len(parts) >= 2:
            room_num = parts[1]
            self._attr_name = f"Thermostat {room_num} Current"
        else:
            self._attr_name = f"{device_info.get('name', 'Thermostat')} Current"
        
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        
        # Device info - use single thermostat grouping
        from .device import EzvilleWallpadDevice
        base_device = EzvilleWallpadDevice(coordinator, device_key, self._attr_unique_id, self._attr_name)
        self._attr_device_info = base_device.device_info
        
        _LOGGER.debug("Initialized thermostat current temperature sensor: %s", self._attr_name)

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        device = self.coordinator.devices.get(self._device_key, {})
        state = device.get("state", {})
        return state.get("current_temperature", 0)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._device_key in self.coordinator.devices

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Update last detected time
        import time
        self._last_detected = time.time()
        
        # Schedule update safely from any thread
        if hasattr(self, 'hass') and self.hass:
            self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)
        else:
            _LOGGER.debug("===> Cannot update state for %s - hass not available", self._attr_name)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Register for direct updates
        self.coordinator.register_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
        _LOGGER.debug("Thermostat current temperature sensor %s added to hass", self._attr_name)

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        # Unregister callback
        self.coordinator.unregister_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
        _LOGGER.debug("Thermostat current temperature sensor %s removed from hass", self._attr_name)


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
        self._attr_unique_id = f"{DOMAIN}_{device_key}_target_temp"
        
        # Extract room number for naming
        parts = device_key.split("_")
        if len(parts) >= 2:
            room_num = parts[1]
            self._attr_name = f"Thermostat {room_num} Target"
        else:
            self._attr_name = f"{device_info.get('name', 'Thermostat')} Target"
        
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        
        # Device info - use single thermostat grouping
        from .device import EzvilleWallpadDevice
        base_device = EzvilleWallpadDevice(coordinator, device_key, self._attr_unique_id, self._attr_name)
        self._attr_device_info = base_device.device_info
        
        _LOGGER.debug("Initialized thermostat target temperature sensor: %s", self._attr_name)

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        device = self.coordinator.devices.get(self._device_key, {})
        state = device.get("state", {})
        return state.get("target_temperature", 0)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._device_key in self.coordinator.devices

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Update last detected time
        import time
        self._last_detected = time.time()
        
        # Schedule update safely from any thread
        if hasattr(self, 'hass') and self.hass:
            self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)
        else:
            _LOGGER.debug("===> Cannot update state for %s - hass not available", self._attr_name)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Register for direct updates
        self.coordinator.register_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
        _LOGGER.debug("Thermostat target temperature sensor %s added to hass", self._attr_name)

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        # Unregister callback
        self.coordinator.unregister_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
        _LOGGER.debug("Thermostat target temperature sensor %s removed from hass", self._attr_name)


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
        if device_id and device_id != "system":
            # device_id is the signature (8 hex chars)
            self._attr_name = f"Unknown {device_id}"
        else:
            self._attr_name = "Unknown"
        self._attr_icon = "mdi:help-circle"
        
        # Device info - use unknown device grouping
        from .device import EzvilleWallpadDevice
        base_device = EzvilleWallpadDevice(coordinator, device_key, self._attr_unique_id, self._attr_name)
        self._attr_device_info = base_device.device_info
        
        # Add timestamp attributes
        import time
        self._first_detected = time.time()
        self._last_detected = time.time()
        
        _LOGGER.debug("Initialized unknown device sensor: %s (device_id: %s)", self._attr_name, device_id)

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
        
        import time
        from datetime import datetime
        
        attributes = {
            "device_id": state.get("device_id", "Unknown"),
            "device_num": state.get("device_num", 0),
            "command": state.get("command", "Unknown"),
            "raw_data": state.get("raw_data", "No data"),
            "signature": state.get("signature", "Unknown"),
            "first_detected": datetime.fromtimestamp(self._first_detected).isoformat(),
            "last_detected": datetime.fromtimestamp(self._last_detected).isoformat()
        }
        
        return attributes

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._device_key in self.coordinator.devices

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Schedule update safely from any thread
        if hasattr(self, 'hass') and self.hass:
            self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)
        else:
            _LOGGER.debug("===> Cannot update state for %s - hass not available", self._attr_name)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Register for direct updates
        self.coordinator.register_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
        _LOGGER.debug("Unknown device sensor %s added to hass", self._attr_name)

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        # Unregister callback
        self.coordinator.unregister_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
        _LOGGER.debug("Unknown device sensor %s removed from hass", self._attr_name)