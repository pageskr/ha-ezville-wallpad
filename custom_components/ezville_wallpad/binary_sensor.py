"""Binary sensor platform for Ezville Wallpad."""
import logging
from datetime import datetime

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
        
        # Register packet listener for this sensor
        self._register_packet_listener()

    def _register_packet_listener(self) -> None:
        """Register to listen for specific packets."""
        # Commands to listen for ring on: 0x13, 0x93
        # Commands to listen for ring off (cancel): 0x11, 0x91
        self._ring_on_commands = [0x13, 0x93]
        self._ring_off_commands = [0x11, 0x91]

    @property
    def is_on(self) -> bool:
        """Return true if doorbell ring is active."""
        return self._is_on

    @callback
    def _handle_packet_update(self, packet_data: dict) -> None:
        """Handle packet updates for this sensor."""
        command = packet_data.get("command", "").lower().replace("0x", "")
        try:
            cmd_int = int(command, 16)
            
            # Check if this is a ring on command
            if cmd_int in self._ring_on_commands:
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
                _LOGGER.info("Doorbell ring turned ON by command 0x%02X", cmd_int)
            
            # Check if this is a ring off (cancel) command
            elif cmd_int in self._ring_off_commands:
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
                _LOGGER.info("Doorbell ring turned OFF by cancel command 0x%02X", cmd_int)
                
        except ValueError:
            pass

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Check for CMD sensor updates
        for device_key, device_data in self.coordinator.devices.items():
            if device_data.get("is_cmd_sensor", False) and "doorbell_cmd_" in device_key:
                state = device_data.get("state", {})
                self._handle_packet_update(state)
        
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
