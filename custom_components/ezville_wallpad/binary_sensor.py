"""Binary sensor platform for Ezville Wallpad."""
import logging
from datetime import datetime, timedelta

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
            # Add ringing sensor (existing)
            entities.append(
                EzvilleDoorbellSensor(
                    coordinator,
                    device_key,
                    device_info
                )
            )
            # Add ring sensor (new)
            entities.append(
                EzvilleDoorbellRingSensor(
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
        self._is_on = False
        self._last_packet_info = None
        self._attr_extra_state_attributes = {}
        
        # Device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_key)},
            "name": device_info.get("name", "Doorbell"),
            "manufacturer": MANUFACTURER,
            "model": MODEL,
        }
        
        # Commands to listen for
        self._ringing_on_commands = [0x12, 0x92]  # Talk commands indicate ringing
        self._ringing_off_commands = [0x11, 0x91, 0x22, 0xA2]  # Cancel/Open commands end ringing

    @property
    def is_on(self) -> bool:
        """Return true if doorbell is ringing."""
        return self._is_on

    def _handle_packet_received(self, command: int, packet_data: dict) -> None:
        """Handle when a relevant packet is received."""
        # Check if update is recent (within 1 second)
        last_seen = packet_data.get("last_seen")
        if last_seen:
            try:
                last_seen_time = datetime.fromisoformat(last_seen)
                current_time = datetime.now()
                time_diff = current_time - last_seen_time
                
                # Only update if within 1 second
                if time_diff > timedelta(seconds=1):
                    _LOGGER.debug("Doorbell ringing sensor skipped old update (%.1f seconds old)", 
                                time_diff.total_seconds())
                    return
            except Exception as e:
                _LOGGER.error("Error processing last_seen time for doorbell ringing sensor: %s", e)
                return
        
        # Check if this is a ringing on command
        if command in self._ringing_on_commands:
            self._is_on = True
            self._last_packet_info = packet_data
            self._attr_extra_state_attributes = {
                "last_ringing": datetime.now().isoformat(),
                "device_id": packet_data.get("device_id", ""),
                "device_num": packet_data.get("device_num", ""),
                "command": packet_data.get("command", ""),
                "raw_data": packet_data.get("data", "")
            }
            self.async_write_ha_state()
            _LOGGER.info("Doorbell ringing turned ON by command 0x%02X", command)
        
        # Check if this is a ringing off command
        elif command in self._ringing_off_commands:
            self._is_on = False
            self._last_packet_info = packet_data
            self._attr_extra_state_attributes.update({
                "last_stop_ringing": datetime.now().isoformat(),
                "device_id": packet_data.get("device_id", ""),
                "device_num": packet_data.get("device_num", ""),
                "command": packet_data.get("command", ""),
                "raw_data": packet_data.get("data", "")
            })
            self.async_write_ha_state()
            _LOGGER.info("Doorbell ringing turned OFF by command 0x%02X", command)

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
                    if command in self._ringing_on_commands or command in self._ringing_off_commands:
                        self._handle_packet_received(command, state)
                except ValueError:
                    pass
        
        # Also handle normal state updates
        super()._handle_coordinator_update()

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


class EzvilleDoorbellRingSensor(CoordinatorEntity, BinarySensorEntity):
    """Ezville Wallpad doorbell ring sensor."""

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
        self._attr_unique_id = f"{DOMAIN}_{device_key}_ring"
        self._attr_name = f"{device_info.get('name', 'Doorbell')} Ring"
        self._attr_device_class = BinarySensorDeviceClass.SOUND
        self._is_on = False
        self._last_packet_info = None
        self._attr_extra_state_attributes = {}
        
        # Device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_key)},
            "name": device_info.get("name", "Doorbell"),
            "manufacturer": MANUFACTURER,
            "model": MODEL,
        }
        
        # Commands to listen for
        self._ring_on_commands = [0x13, 0x93]
        self._ring_off_commands = [0x11, 0x91]

    @property
    def is_on(self) -> bool:
        """Return true if doorbell ring is active."""
        return self._is_on

    def _handle_packet_received(self, command: int, packet_data: dict) -> None:
        """Handle when a relevant packet is received."""
        # Check if update is recent (within 1 second)
        last_seen = packet_data.get("last_seen")
        if last_seen:
            try:
                last_seen_time = datetime.fromisoformat(last_seen)
                current_time = datetime.now()
                time_diff = current_time - last_seen_time
                
                # Only update if within 1 second
                if time_diff > timedelta(seconds=1):
                    _LOGGER.debug("Doorbell ring sensor skipped old update (%.1f seconds old)", 
                                time_diff.total_seconds())
                    return
            except Exception as e:
                _LOGGER.error("Error processing last_seen time for doorbell ring sensor: %s", e)
                return
        
        # Check if this is a ring on command
        if command in self._ring_on_commands:
            self._is_on = True
            self._last_packet_info = packet_data
            self._attr_extra_state_attributes = {
                "last_ring": datetime.now().isoformat(),
                "device_id": packet_data.get("device_id", ""),
                "device_num": packet_data.get("device_num", ""),
                "command": packet_data.get("command", ""),
                "raw_data": packet_data.get("data", "")
            }
            self.async_write_ha_state()
            _LOGGER.info("Doorbell ring turned ON by command 0x%02X", command)
        
        # Check if this is a ring off (cancel) command
        elif command in self._ring_off_commands:
            self._is_on = False
            self._last_packet_info = packet_data
            self._attr_extra_state_attributes.update({
                "last_cancel": datetime.now().isoformat(),
                "device_id": packet_data.get("device_id", ""),
                "device_num": packet_data.get("device_num", ""),
                "command": packet_data.get("command", ""),
                "raw_data": packet_data.get("data", "")
            })
            self.async_write_ha_state()
            _LOGGER.info("Doorbell ring turned OFF by cancel command 0x%02X", command)

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
                    if command in self._ring_on_commands or command in self._ring_off_commands:
                        self._handle_packet_received(command, state)
                except ValueError:
                    pass
        
        # Also handle normal state updates
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        
        # Register for normal device updates
        self.coordinator.register_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # This is for normal state updates from the device
        super()._handle_coordinator_update()

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        # Unregister normal callback
        self.coordinator.unregister_entity_callback(
            self._device_key,
            self._handle_coordinator_update
        )
