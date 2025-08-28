"""Button platform for Ezville Wallpad."""
import logging
from typing import Any
from datetime import datetime

from homeassistant.components.button import ButtonEntity
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


class EzvilleDoorbellCallButton(CoordinatorEntity, ButtonEntity):
    """Ezville Wallpad doorbell call button."""

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
        self._attr_name = f"{device_info.get('name', 'Doorbell')} Call"
        self._last_packet_info = None
        self._attr_extra_state_attributes = {}
        
        # Device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_key)},
            "name": device_info.get("name", "Doorbell"),
            "manufacturer": MANUFACTURER,
            "model": MODEL,
        }
        
        # Register packet listener for this button
        self._register_packet_listener()

    def _register_packet_listener(self) -> None:
        """Register to listen for specific packets."""
        # Commands to listen for: 0x10, 0x90
        self._listen_commands = [0x10, 0x90]
        
    @callback
    def _handle_packet_update(self, packet_data: dict) -> None:
        """Handle packet updates for this button."""
        command = packet_data.get("command", "").lower().replace("0x", "")
        try:
            cmd_int = int(command, 16)
            if cmd_int in self._listen_commands:
                self._last_packet_info = packet_data
                self._attr_extra_state_attributes = {
                    "last_pressed": datetime.now().isoformat(),
                    "device_id": packet_data.get("device_id", ""),
                    "device_num": packet_data.get("device_num", ""),
                    "command": packet_data.get("command", ""),
                    "raw_data": packet_data.get("data", "")
                }
                self.async_write_ha_state()
        except ValueError:
            pass

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.send_command(
            "doorbell",
            self._device_info["device_id"],
            "call",
            True
        )
        _LOGGER.info("Doorbell call button pressed")

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Check for CMD sensor updates
        for device_key, device_data in self.coordinator.devices.items():
            if device_data.get("is_cmd_sensor", False) and "doorbell_cmd_" in device_key:
                state = device_data.get("state", {})
                self._handle_packet_update(state)
        
        super()._handle_coordinator_update()


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
        self._last_packet_info = None
        self._attr_extra_state_attributes = {}
        
        # Device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_key)},
            "name": device_info.get("name", "Doorbell"),
            "manufacturer": MANUFACTURER,
            "model": MODEL,
        }
        
        # Register packet listener for this button
        self._register_packet_listener()

    def _register_packet_listener(self) -> None:
        """Register to listen for specific packets."""
        # Commands to listen for: 0x12, 0x92
        self._listen_commands = [0x12, 0x92]
        
    @callback
    def _handle_packet_update(self, packet_data: dict) -> None:
        """Handle packet updates for this button."""
        command = packet_data.get("command", "").lower().replace("0x", "")
        try:
            cmd_int = int(command, 16)
            if cmd_int in self._listen_commands:
                self._last_packet_info = packet_data
                self._attr_extra_state_attributes = {
                    "last_pressed": datetime.now().isoformat(),
                    "device_id": packet_data.get("device_id", ""),
                    "device_num": packet_data.get("device_num", ""),
                    "command": packet_data.get("command", ""),
                    "raw_data": packet_data.get("data", "")
                }
                self.async_write_ha_state()
        except ValueError:
            pass

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.send_command(
            "doorbell",
            self._device_info["device_id"],
            "talk",
            True
        )
        _LOGGER.info("Doorbell talk button pressed")

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Check for CMD sensor updates
        for device_key, device_data in self.coordinator.devices.items():
            if device_data.get("is_cmd_sensor", False) and "doorbell_cmd_" in device_key:
                state = device_data.get("state", {})
                self._handle_packet_update(state)
        
        super()._handle_coordinator_update()


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
        self._last_packet_info = None
        self._attr_extra_state_attributes = {}
        
        # Device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_key)},
            "name": device_info.get("name", "Doorbell"),
            "manufacturer": MANUFACTURER,
            "model": MODEL,
        }
        
        # Register packet listener for this button
        self._register_packet_listener()

    def _register_packet_listener(self) -> None:
        """Register to listen for specific packets."""
        # Commands to listen for: 0x22, 0xA2
        self._listen_commands = [0x22, 0xA2]
        
    @callback
    def _handle_packet_update(self, packet_data: dict) -> None:
        """Handle packet updates for this button."""
        command = packet_data.get("command", "").lower().replace("0x", "")
        try:
            cmd_int = int(command, 16)
            if cmd_int in self._listen_commands:
                self._last_packet_info = packet_data
                self._attr_extra_state_attributes = {
                    "last_pressed": datetime.now().isoformat(),
                    "device_id": packet_data.get("device_id", ""),
                    "device_num": packet_data.get("device_num", ""),
                    "command": packet_data.get("command", ""),
                    "raw_data": packet_data.get("data", "")
                }
                self.async_write_ha_state()
        except ValueError:
            pass

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.send_command(
            "doorbell",
            self._device_info["device_id"],
            "open",
            True
        )
        _LOGGER.info("Doorbell open button pressed")

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Check for CMD sensor updates
        for device_key, device_data in self.coordinator.devices.items():
            if device_data.get("is_cmd_sensor", False) and "doorbell_cmd_" in device_key:
                state = device_data.get("state", {})
                self._handle_packet_update(state)
        
        super()._handle_coordinator_update()


class EzvilleDoorbellCancelButton(CoordinatorEntity, ButtonEntity):
    """Ezville Wallpad doorbell cancel button."""

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
        self._attr_unique_id = f"{DOMAIN}_{device_key}_cancel"
        self._attr_name = f"{device_info.get('name', 'Doorbell')} Cancel"
        self._last_packet_info = None
        self._attr_extra_state_attributes = {}
        
        # Device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_key)},
            "name": device_info.get("name", "Doorbell"),
            "manufacturer": MANUFACTURER,
            "model": MODEL,
        }
        
        # Register packet listener for this button
        self._register_packet_listener()

    def _register_packet_listener(self) -> None:
        """Register to listen for specific packets."""
        # Commands to listen for: 0x11, 0x91
        self._listen_commands = [0x11, 0x91]
        
    @callback
    def _handle_packet_update(self, packet_data: dict) -> None:
        """Handle packet updates for this button."""
        command = packet_data.get("command", "").lower().replace("0x", "")
        try:
            cmd_int = int(command, 16)
            if cmd_int in self._listen_commands:
                self._last_packet_info = packet_data
                self._attr_extra_state_attributes = {
                    "last_pressed": datetime.now().isoformat(),
                    "device_id": packet_data.get("device_id", ""),
                    "device_num": packet_data.get("device_num", ""),
                    "command": packet_data.get("command", ""),
                    "raw_data": packet_data.get("data", "")
                }
                self.async_write_ha_state()
        except ValueError:
            pass

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.send_command(
            "doorbell",
            self._device_info["device_id"],
            "cancel",
            True
        )
        _LOGGER.info("Doorbell cancel button pressed")

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Check for CMD sensor updates
        for device_key, device_data in self.coordinator.devices.items():
            if device_data.get("is_cmd_sensor", False) and "doorbell_cmd_" in device_key:
                state = device_data.get("state", {})
                self._handle_packet_update(state)
        
        super()._handle_coordinator_update()
