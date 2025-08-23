"""Button platform for Ezville Wallpad."""
import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import EzvilleWallpadCoordinator

_LOGGER = logging.getLogger("custom_components.ezville_wallpad.button")


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ezville Wallpad buttons."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    
    # Add elevator buttons
    if "elevator" in coordinator.capabilities:
        for device_key, device_info in coordinator.devices.items():
            if device_info["device_type"] == "elevator":
                entities.append(
                    EzvilleElevatorCallButton(
                        coordinator,
                        device_key,
                        device_info
                    )
                )
    
    # Add doorbell buttons
    if "doorbell" in coordinator.capabilities:
        for device_key, device_info in coordinator.devices.items():
            if device_info["device_type"] == "doorbell":
                entities.extend([
                    EzvilleDoorbellOpenButton(
                        coordinator,
                        device_key,
                        device_info
                    ),
                    EzvilleDoorbellTalkButton(
                        coordinator,
                        device_key,
                        device_info
                    ),
                ])
    
    if entities:
        async_add_entities(entities)
        _LOGGER.info("Added %d button entities", len(entities))


class EzvilleElevatorCallButton(CoordinatorEntity, ButtonEntity):
    """Ezville Wallpad elevator call button."""

    def __init__(
        self,
        coordinator: EzvilleWallpadCoordinator,
        device_key: str,
        device_info: dict,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._device_key = device_key
        self._device_info = device_info
        self._attr_unique_id = f"{DOMAIN}_{device_key}_call"
        self._attr_name = f"{device_info.get('name', 'Elevator')} Call"
        
        # Device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_key)},
            "name": device_info.get("name", "Elevator"),
            "manufacturer": MANUFACTURER,
            "model": MODEL,
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.send_command(
            "elevator",
            self._device_info["device_id"],
            "call",
            True
        )
        _LOGGER.info("Elevator call button pressed")


class EzvilleDoorbellOpenButton(CoordinatorEntity, ButtonEntity):
    """Ezville Wallpad doorbell open button."""

    def __init__(
        self,
        coordinator: EzvilleWallpadCoordinator,
        device_key: str,
        device_info: dict,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._device_key = device_key
        self._device_info = device_info
        self._attr_unique_id = f"{DOMAIN}_{device_key}_open"
        self._attr_name = f"{device_info.get('name', 'Doorbell')} Open"
        
        # Device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_key)},
            "name": device_info.get("name", "Doorbell"),
            "manufacturer": MANUFACTURER,
            "model": MODEL,
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.send_command(
            "doorbell",
            self._device_info["device_id"],
            "open",
            True
        )
        _LOGGER.info("Doorbell open button pressed")


class EzvilleDoorbellTalkButton(CoordinatorEntity, ButtonEntity):
    """Ezville Wallpad doorbell talk button."""

    def __init__(
        self,
        coordinator: EzvilleWallpadCoordinator,
        device_key: str,
        device_info: dict,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._device_key = device_key
        self._device_info = device_info
        self._attr_unique_id = f"{DOMAIN}_{device_key}_talk"
        self._attr_name = f"{device_info.get('name', 'Doorbell')} Talk"
        
        # Device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_key)},
            "name": device_info.get("name", "Doorbell"),
            "manufacturer": MANUFACTURER,
            "model": MODEL,
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.send_command(
            "doorbell",
            self._device_info["device_id"],
            "talk",
            True
        )
        _LOGGER.info("Doorbell talk button pressed")
