"""Sensor platform for Ezville Wallpad."""
import logging
from typing import Any, Optional

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower, UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
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
        
        # Add plug power sensor
        if device_info["device_type"] == "plug" and f"{device_key}_power" not in added_devices:
            added_devices.add(f"{device_key}_power")
            entities.append(EzvillePowerSensor(coordinator, device_key, device_info))
            _LOGGER.info("Added power sensor for %s", device_key)
        
        # Add energy monitor sensor
        if device_info["device_type"] == "energy" and f"{device_key}_energy" not in added_devices:
            added_devices.add(f"{device_key}_energy")
            entities.append(EzvilleEnergySensor(coordinator, device_key, device_info))
            _LOGGER.info("Added energy sensor for %s", device_key)
        
        # Add unknown device sensor
        if device_info["device_type"] == "unknown" and f"{device_key}_unknown" not in added_devices:
            added_devices.add(f"{device_key}_unknown")
            entities.append(EzvilleUnknownSensor(coordinator, device_key, device_info))
            _LOGGER.info("Added unknown device sensor for %s", device_key)
        
        if entities:
            async_add_entities(entities)
    
    # Add existing devices
    for device_key, device_info in coordinator.devices.items():
        if device_info["device_type"] in ["plug", "energy", "unknown"]:
            async_add_sensors(device_key, device_info)
    
    # Register callback for new devices
    @callback
    def device_added():
        """Handle new device added."""
        for device_key, device_info in coordinator.devices.items():
            if device_info["device_type"] in ["plug", "energy", "unknown"]:
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


class EzvilleEnergySensor(CoordinatorEntity, SensorEntity):
    """Ezville Wallpad energy monitor sensor."""

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
        self._attr_unique_id = f"{DOMAIN}_{device_key}_energy"
        self._attr_name = "Energy Meter"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        
        # Device info from coordinator
        self._attr_device_info = coordinator.get_device_info(device_key)
        
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
        # Create entity name with signature
        if device_id and device_id != "system":
            self._attr_name = f"Unknown {device_id}"
        else:
            self._attr_name = "Unknown"
        self._attr_icon = "mdi:help-circle"
        
        # Device info from coordinator
        self._attr_device_info = coordinator.get_device_info(device_key)
        
        _LOGGER.debug("Initialized unknown device sensor: %s", self._attr_name)

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
            "device_num": state.get("device_num", 0),
            "command": state.get("command", "Unknown"),
            "raw_data": state.get("raw_data", "No data")
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