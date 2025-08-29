"""Button platform for Ezville Wallpad."""
import logging
from typing import Any
from datetime import datetime

from homeassistant.components.button import ButtonEntity, ENTITY_ID_FORMAT
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
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
                # Skip if is_cmd_sensor exists and is True
                # (But don't skip for normal doorbell devices)
                if device_info.get("is_cmd_sensor", False):
                    continue
                    
                entities.extend([
                    EzvilleDoorbellCallButton(
                        coordinator,
                        device_key,
                        device_info
                    ),
                    EzvilleDoorbellTalkButton(
                        coordinator,
                        device_key,
                        device_info
                    ),
                    EzvilleDoorbellOpenButton(
                        coordinator,
                        device_key,
                        device_info
                    ),
                    EzvilleDoorbellCancelButton(
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


class EzvilleDoorbellButtonBase(CoordinatorEntity, ButtonEntity):
    """Base class for Ezville doorbell buttons."""

    def __init__(
        self,
        coordinator: EzvilleWallpadCoordinator,
        device_key: str,
        device_info: dict,
        button_type: str,
        button_name: str,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._device_key = device_key
        self._device_info = device_info
        self._button_type = button_type
        self._attr_unique_id = f"{DOMAIN}_{device_key}_{button_type}"
        self._attr_name = f"{device_info.get('name', 'Doorbell')} {button_name}"
        self._last_pressed = None
        self._packet_info = {}
        self._listen_commands = []
        
        # Device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_key)},
            "name": device_info.get("name", "Doorbell"),
            "manufacturer": MANUFACTURER,
            "model": MODEL,
        }

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        attrs = {}
        if self._last_pressed:
            attrs["last_pressed"] = self._last_pressed
        if self._packet_info:
            attrs.update(self._packet_info)
        return attrs

    def _handle_packet_received(self, command: int, packet_data: dict) -> None:
        """Handle when a relevant packet is received."""
        if command in self._listen_commands:
            self._last_pressed = datetime.now().isoformat()
            self._packet_info = {
                "device_id": packet_data.get("device_id", ""),
                "device_num": packet_data.get("device_num", ""),
                "command": packet_data.get("command", ""),
                "raw_data": packet_data.get("data", "")
            }
            # Force update state to reflect the button press time
            self.async_write_ha_state()
            _LOGGER.info("Doorbell %s button event detected from command 0x%02X", self._button_type, command)

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Check for doorbell CMD updates
        for device_key in list(self.coordinator.devices.keys()):
            if device_key.startswith("doorbell_cmd_"):
                device_data = self.coordinator.devices.get(device_key, {})
                state = device_data.get("state", {})
                command_str = state.get("command", "").lower().replace("0x", "")
                try:
                    command = int(command_str, 16)
                    if command in self._listen_commands:
                        self._handle_packet_received(command, state)
                except ValueError:
                    pass
        
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        
        # No need to register individual callbacks - coordinator update will catch CMD events

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        # Unregister callbacks
        for cmd in self._listen_commands:
            temp_key = f"doorbell_cmd_{cmd:02X}_temp"
            # Note: We can't easily unregister specific callbacks, but they'll be cleaned up when coordinator is destroyed


class EzvilleDoorbellCallButton(EzvilleDoorbellButtonBase):
    """Ezville Wallpad doorbell call button."""

    def __init__(
        self,
        coordinator: EzvilleWallpadCoordinator,
        device_key: str,
        device_info: dict,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, device_key, device_info, "call", "Call")
        # Commands to listen for: 0x10, 0x90
        self._listen_commands = [0x10, 0x90]

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.send_command(
            "doorbell",
            self._device_info["device_id"],
            "call",
            True
        )
        # Update button press time
        self._last_pressed = datetime.now().isoformat()
        self.async_write_ha_state()
        _LOGGER.info("Doorbell call button pressed")


class EzvilleDoorbellTalkButton(EzvilleDoorbellButtonBase):
    """Ezville Wallpad doorbell talk button."""

    def __init__(
        self,
        coordinator: EzvilleWallpadCoordinator,
        device_key: str,
        device_info: dict,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, device_key, device_info, "talk", "Talk")
        # Commands to listen for: 0x12, 0x92
        self._listen_commands = [0x12, 0x92]

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.send_command(
            "doorbell",
            self._device_info["device_id"],
            "talk",
            True
        )
        # Update button press time
        self._last_pressed = datetime.now().isoformat()
        self.async_write_ha_state()
        _LOGGER.info("Doorbell talk button pressed")


class EzvilleDoorbellOpenButton(EzvilleDoorbellButtonBase):
    """Ezville Wallpad doorbell open button."""

    def __init__(
        self,
        coordinator: EzvilleWallpadCoordinator,
        device_key: str,
        device_info: dict,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, device_key, device_info, "open", "Open")
        # Commands to listen for: 0x22, 0xA2
        self._listen_commands = [0x22, 0xA2]

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.send_command(
            "doorbell",
            self._device_info["device_id"],
            "open",
            True
        )
        # Update button press time
        self._last_pressed = datetime.now().isoformat()
        self.async_write_ha_state()
        _LOGGER.info("Doorbell open button pressed")


class EzvilleDoorbellCancelButton(EzvilleDoorbellButtonBase):
    """Ezville Wallpad doorbell cancel button."""

    def __init__(
        self,
        coordinator: EzvilleWallpadCoordinator,
        device_key: str,
        device_info: dict,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, device_key, device_info, "cancel", "Cancel")
        # Commands to listen for: 0x11, 0x91
        self._listen_commands = [0x11, 0x91]

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.send_command(
            "doorbell",
            self._device_info["device_id"],
            "cancel",
            True
        )
        # Update button press time
        self._last_pressed = datetime.now().isoformat()
        self.async_write_ha_state()
        _LOGGER.info("Doorbell cancel button pressed")
