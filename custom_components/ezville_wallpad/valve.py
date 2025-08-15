"""Valve platform for Ezville Wallpad."""
import logging
from typing import Any

from homeassistant.components.valve import (
    ValveEntity,
    ValveEntityFeature,
    ValveDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import EzvilleWallpadCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ezville Wallpad valves."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    # Check if gas valves are enabled
    if "gas" not in coordinator.capabilities:
        return
    
    entities = []
    for device_key, device_info in coordinator.devices.items():
        if device_info["device_type"] == "gas":
            entities.append(
                EzvilleGasValve(
                    coordinator,
                    device_key,
                    device_info
                )
            )
    
    if entities:
        async_add_entities(entities)
        _LOGGER.info("Added %d valve entities", len(entities))


class EzvilleGasValve(CoordinatorEntity, ValveEntity):
    """Ezville Wallpad gas valve entity."""

    def __init__(
        self,
        coordinator: EzvilleWallpadCoordinator,
        device_key: str,
        device_info: dict,
    ) -> None:
        """Initialize the valve."""
        super().__init__(coordinator)
        self._device_key = device_key
        self._device_info = device_info
        self._attr_unique_id = f"{DOMAIN}_{device_key}"
        self._attr_name = "Gas Valve Close"
        self._attr_device_class = ValveDeviceClass.GAS
        
        # Set capabilities
        self._attr_supported_features = (
            ValveEntityFeature.OPEN |
            ValveEntityFeature.CLOSE
        )
        
        # Device info는 base class에서 처리하도록 함
        self._attr_device_info = coordinator.get_device_info(device_key)

    @property
    def is_closed(self) -> bool:
        """Return true if valve is closed."""
        device = self.coordinator.devices.get(self._device_key, {})
        state = device.get("state", {})
        return state.get("closed", True)

    @property
    def is_closing(self) -> bool:
        """Return true if valve is closing."""
        return False

    @property
    def is_opening(self) -> bool:
        """Return true if valve is opening."""
        return False

    async def async_open_valve(self, **kwargs: Any) -> None:
        """Open the valve."""
        await self.coordinator.send_command(
            "gas",
            self._device_info["device_id"],
            "close",
            False
        )
        
        # Update local state immediately
        if self._device_key in self.coordinator.devices:
            self.coordinator.devices[self._device_key]["state"]["closed"] = False
        
        self.async_write_ha_state()

    async def async_close_valve(self, **kwargs: Any) -> None:
        """Close the valve."""
        await self.coordinator.send_command(
            "gas",
            self._device_info["device_id"],
            "close",
            True
        )
        
        # Update local state immediately
        if self._device_key in self.coordinator.devices:
            self.coordinator.devices[self._device_key]["state"]["closed"] = True
        
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

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
