"""Fan platform for Ezville Wallpad."""
import logging
from typing import Any, Optional
import math

from homeassistant.components.fan import (
    FanEntity,
    FanEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import EzvilleWallpadCoordinator

_LOGGER = logging.getLogger("custom_components.ezville_wallpad.fan")

SPEED_RANGE = (1, 3)  # 3 speed levels


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ezville Wallpad fans."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    # Check if fans are enabled
    if "fan" not in coordinator.capabilities:
        return
    
    entities = []
    for device_key, device_info in coordinator.devices.items():
        if device_info["device_type"] == "fan":
            entities.append(
                EzvilleFan(
                    coordinator,
                    device_key,
                    device_info
                )
            )
    
    if entities:
        async_add_entities(entities)
        _LOGGER.info("Added %d fan entities", len(entities))


class EzvilleFan(CoordinatorEntity, FanEntity):
    """Ezville Wallpad fan entity."""

    def __init__(
        self,
        coordinator: EzvilleWallpadCoordinator,
        device_key: str,
        device_info: dict,
    ) -> None:
        """Initialize the fan."""
        super().__init__(coordinator)
        self._device_key = device_key
        self._device_info = device_info
        self._attr_unique_id = f"{DOMAIN}_{device_key}"
        self._attr_name = "Ventilation Fan"
        
        # Set capabilities
        self._attr_supported_features = (
            FanEntityFeature.SET_SPEED |
            FanEntityFeature.TURN_ON |
            FanEntityFeature.TURN_OFF |
            FanEntityFeature.PRESET_MODE
        )
        
        # Preset modes
        self._attr_preset_modes = ["bypass", "heat"]
        
        # Device info는 base class에서 처리하도록 함
        self._attr_device_info = coordinator.get_device_info(device_key)

    @property
    def is_on(self) -> bool:
        """Return true if fan is on."""
        device = self.coordinator.devices.get(self._device_key, {})
        state = device.get("state", {})
        return state.get("power", False)

    @property
    def percentage(self) -> Optional[int]:
        """Return the current speed percentage."""
        device = self.coordinator.devices.get(self._device_key, {})
        state = device.get("state", {})
        speed = state.get("speed", 0)
        
        if speed == 0:
            return 0
        
        return ranged_value_to_percentage(SPEED_RANGE, speed)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return SPEED_RANGE[1]
    
    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode."""
        device = self.coordinator.devices.get(self._device_key, {})
        state = device.get("state", {})
        mode = state.get("mode", "bypass")
        # Ensure the mode is in our supported list
        if mode in self._attr_preset_modes:
            return mode
        return "bypass"

    async def async_turn_on(
        self,
        percentage: Optional[int] = None,
        preset_mode: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        await self.coordinator.send_command(
            "fan",
            self._device_info["device_id"],
            "power",
            True
        )
        
        # Set speed if specified
        if percentage is not None:
            await self.async_set_percentage(percentage)
            
        # Set preset mode if specified
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        
        # Update local state immediately
        if self._device_key in self.coordinator.devices:
            self.coordinator.devices[self._device_key]["state"]["power"] = True
        
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        await self.coordinator.send_command(
            "fan",
            self._device_info["device_id"],
            "power",
            False
        )
        
        # Update local state immediately
        if self._device_key in self.coordinator.devices:
            self.coordinator.devices[self._device_key]["state"]["power"] = False
        
        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            await self.async_turn_off()
            return
        
        speed = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
        
        await self.coordinator.send_command(
            "fan",
            self._device_info["device_id"],
            "speed",
            speed
        )
        
        # Update local state immediately
        if self._device_key in self.coordinator.devices:
            self.coordinator.devices[self._device_key]["state"]["speed"] = speed
            if not self.is_on:
                self.coordinator.devices[self._device_key]["state"]["power"] = True
        
        self.async_write_ha_state()
    
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode not in self._attr_preset_modes:
            return
            
        await self.coordinator.send_command(
            "fan",
            self._device_info["device_id"],
            "mode",
            preset_mode
        )
        
        # Update local state immediately
        if self._device_key in self.coordinator.devices:
            self.coordinator.devices[self._device_key]["state"]["mode"] = preset_mode
        
        self.async_write_ha_state()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Schedule update safely from any thread
        if hasattr(self, 'hass') and self.hass:
            self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)
        else:
            _LOGGER.debug("Cannot update state - hass not available")

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
