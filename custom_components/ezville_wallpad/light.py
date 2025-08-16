"""Light platform for Ezville Wallpad."""
import logging
from typing import Any, Optional

from homeassistant.components.light import (
    LightEntity,
    ColorMode,
    ATTR_BRIGHTNESS,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EzvilleWallpadCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ezville Wallpad lights."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    # Check if lights are enabled
    if "light" not in coordinator.capabilities:
        _LOGGER.debug("Light capability not enabled")
        return
    
    _LOGGER.info("Setting up light platform")
    
    # Track added entities
    added_devices = set()
    
    @callback
    def async_add_light(device_key: str, device_info: dict):
        """Add new light entity."""
        if device_key not in added_devices:
            added_devices.add(device_key)
            entity = EzvilleLight(coordinator, device_key, device_info)
            async_add_entities([entity])
            _LOGGER.info("Added light entity: %s", device_key)
    
    # Add existing devices
    for device_key, device_info in coordinator.devices.items():
        if device_info["device_type"] == "light":
            async_add_light(device_key, device_info)
    
    # Register callback for new devices
    @callback
    def device_added():
        """Handle new device added."""
        for device_key, device_info in coordinator.devices.items():
            if device_info["device_type"] == "light" and device_key not in added_devices:
                async_add_light(device_key, device_info)
    
    # Listen for coordinator updates
    coordinator.async_add_listener(device_added)
    
    _LOGGER.info("Light platform setup complete with %d entities", len(added_devices))


class EzvilleLight(CoordinatorEntity, LightEntity):
    """Ezville Wallpad light entity."""

    def __init__(
        self,
        coordinator: EzvilleWallpadCoordinator,
        device_key: str,
        device_info: dict,
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator)
        self._device_key = device_key
        self._device_info = device_info
        self._attr_unique_id = f"{DOMAIN}_{device_key}"
        # 구성요소 이름 설정 (Light 1 1, Light 1 2 형식)
        parts = device_key.split("_")
        if len(parts) == 3:
            room_num = parts[1]
            light_num = parts[2]
            self._attr_name = f"Light {room_num} {light_num}"
        else:
            self._attr_name = device_info.get("name", f"Light {device_info['device_id']}")
        self._attr_color_mode = ColorMode.BRIGHTNESS
        self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        
        # Device info - use room-based grouping
        from .device import EzvilleWallpadDevice
        base_device = EzvilleWallpadDevice(coordinator, device_key, self._attr_unique_id, self._attr_name)
        self._attr_device_info = base_device.device_info
        
        _LOGGER.debug("Initialized light entity: %s", self._attr_name)

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        device = self.coordinator.devices.get(self._device_key, {})
        state = device.get("state", {})
        return state.get("power", False)

    @property
    def brightness(self) -> Optional[int]:
        """Return the brightness of the light."""
        device = self.coordinator.devices.get(self._device_key, {})
        state = device.get("state", {})
        # Convert 0-100 to 0-255
        brightness_percent = state.get("brightness", 0)
        return int(brightness_percent * 255 / 100)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._device_key in self.coordinator.devices

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        _LOGGER.debug("Turning on light %s", self._device_key)
        
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        
        # Send power on command
        await self.coordinator.send_command(
            "light",
            self._device_info["device_id"],
            "power",
            True
        )
        
        # If brightness is specified, send brightness command
        if brightness is not None:
            brightness_percent = int(brightness * 100 / 255)
            _LOGGER.debug("Setting brightness to %d%%", brightness_percent)
            # This would need a separate brightness command implementation
        
        # Update local state immediately for responsiveness
        if self._device_key in self.coordinator.devices:
            self.coordinator.devices[self._device_key]["state"]["power"] = True
            if brightness is not None:
                self.coordinator.devices[self._device_key]["state"]["brightness"] = int(brightness * 100 / 255)
        
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        _LOGGER.debug("Turning off light %s", self._device_key)
        
        await self.coordinator.send_command(
            "light",
            self._device_info["device_id"],
            "power",
            False
        )
        
        # Update local state immediately
        if self._device_key in self.coordinator.devices:
            self.coordinator.devices[self._device_key]["state"]["power"] = False
        
        self.async_write_ha_state()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Schedule update safely from any thread
        if hasattr(self, 'hass') and self.hass:
            self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)
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
        _LOGGER.debug("Light entity %s added to hass", self._attr_name)

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        # Unregister callback
        self.coordinator.unregister_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
        _LOGGER.debug("Light entity %s removed from hass", self._attr_name)