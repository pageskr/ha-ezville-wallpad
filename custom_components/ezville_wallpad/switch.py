"""Switch platform for Ezville Wallpad."""
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    """Set up Ezville Wallpad switches."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    # Check if plugs are enabled
    if "plug" not in coordinator.capabilities:
        _LOGGER.debug("Plug capability not enabled")
        return
    
    _LOGGER.info("Setting up switch platform")
    
    # Track added entities
    added_devices = set()
    
    @callback
    def async_add_switch(device_key: str, device_info: dict):
        """Add new switch entity."""
        if device_key not in added_devices:
            added_devices.add(device_key)
            entity = EzvilleSwitch(coordinator, device_key, device_info)
            async_add_entities([entity])
            _LOGGER.info("Added switch entity: %s", device_key)
    
    # Add existing devices
    for device_key, device_info in coordinator.devices.items():
        if device_info["device_type"] == "plug":
            async_add_switch(device_key, device_info)
    
    # Register callback for new devices
    @callback
    def device_added():
        """Handle new device added."""
        for device_key, device_info in coordinator.devices.items():
            if device_info["device_type"] == "plug" and device_key not in added_devices:
                async_add_switch(device_key, device_info)
    
    # Listen for coordinator updates
    coordinator.async_add_listener(device_added)
    
    _LOGGER.info("Switch platform setup complete with %d entities", len(added_devices))


class EzvilleSwitch(CoordinatorEntity, SwitchEntity):
    """Ezville Wallpad switch entity."""

    def __init__(
        self,
        coordinator: EzvilleWallpadCoordinator,
        device_key: str,
        device_info: dict,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._device_key = device_key
        self._device_info = device_info
        self._attr_unique_id = f"{DOMAIN}_{device_key}"
        # 구성요소 이름 설정 (Plug 1 1, Plug 1 2 형식)
        parts = device_key.split("_")
        if len(parts) == 3:
            room_num = parts[1]
            plug_num = parts[2]
            self._attr_name = f"Plug {room_num} {plug_num}"
        else:
            self._attr_name = device_info.get("name", f"Plug {device_info['device_id']}")
        
        # Device info from coordinator
        self._attr_device_info = coordinator.get_device_info(device_key)
        
        _LOGGER.debug("Initialized switch entity: %s", self._attr_name)

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        device = self.coordinator.devices.get(self._device_key, {})
        state = device.get("state", {})
        return state.get("power", False)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._device_key in self.coordinator.devices

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        _LOGGER.debug("Turning on switch %s", self._device_key)
        
        await self.coordinator.send_command(
            "plug",
            self._device_info["device_id"],
            "power",
            True
        )
        
        # Update local state immediately for responsiveness
        if self._device_key in self.coordinator.devices:
            self.coordinator.devices[self._device_key]["state"]["power"] = True
        
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        _LOGGER.debug("Turning off switch %s", self._device_key)
        
        await self.coordinator.send_command(
            "plug",
            self._device_info["device_id"],
            "power",
            False
        )
        
        # Update local state immediately
        if self._device_key in self.coordinator.devices:
            self.coordinator.devices[self._device_key]["state"]["power"] = False
        
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
        _LOGGER.debug("Switch entity %s added to hass", self._attr_name)

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        # Unregister callback
        self.coordinator.unregister_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
        _LOGGER.debug("Switch entity %s removed from hass", self._attr_name)