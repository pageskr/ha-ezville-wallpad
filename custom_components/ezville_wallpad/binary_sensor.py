"""Binary sensor platform for Ezville Wallpad."""
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import EzvilleWallpadCoordinator

_LOGGER = logging.getLogger("custom_components.ezville_wallpad.binary_sensor")


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ezville Wallpad binary sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    # Check if doorbells are enabled
    if "doorbell" not in coordinator.capabilities:
        return
    
    entities = []
    for device_key, device_info in coordinator.devices.items():
        # Skip CMD sensors
        if device_info.get("is_cmd_sensor", False):
            continue
        if device_info["device_type"] == "doorbell":
            entities.append(
                EzvilleDoorbellSensor(
                    coordinator,
                    device_key,
                    device_info
                )
            )
    
    if entities:
        async_add_entities(entities)
        _LOGGER.info("Added %d binary sensor entities", len(entities))


class EzvilleDoorbellSensor(CoordinatorEntity, BinarySensorEntity):
    """Ezville Wallpad doorbell sensor."""

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
        self._attr_unique_id = f"{DOMAIN}_{device_key}_ringing"
        self._attr_name = f"{device_info.get('name', 'Doorbell')} Ringing"
        self._attr_device_class = BinarySensorDeviceClass.OCCUPANCY
        
        # Device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_key)},
            "name": device_info.get("name", "Doorbell"),
            "manufacturer": MANUFACTURER,
            "model": MODEL,
        }

    @property
    def is_on(self) -> bool:
        """Return true if doorbell is ringing."""
        device = self.coordinator.devices.get(self._device_key, {})
        state = device.get("state", {})
        return state.get("ringing", False)

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Schedule update safely from any thread
        if hasattr(self, 'hass') and self.hass:
            self.hass.loop.call_soon_threadsafe(lambda: self.schedule_update_ha_state(True))
        else:
            _LOGGER.warning("Cannot update state - hass not available")

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Register for direct updates
        self.coordinator.register_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        # Unregister callback
        self.coordinator.unregister_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
