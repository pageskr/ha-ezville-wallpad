"""Climate platform for Ezville Wallpad."""
import logging
from typing import Any, Optional, List

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    UnitOfTemperature,
)
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
    """Set up Ezville Wallpad climate entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    # Check if thermostats are enabled
    if "thermostat" not in coordinator.capabilities:
        return
    
    entities = []
    for device_key, device_info in coordinator.devices.items():
        if device_info["device_type"] == "thermostat":
            entities.append(
                EzvilleThermostat(
                    coordinator,
                    device_key,
                    device_info
                )
            )
    
    if entities:
        async_add_entities(entities)
        _LOGGER.info("Added %d climate entities", len(entities))


class EzvilleThermostat(CoordinatorEntity, ClimateEntity):
    """Ezville Wallpad thermostat entity."""

    def __init__(
        self,
        coordinator: EzvilleWallpadCoordinator,
        device_key: str,
        device_info: dict,
    ) -> None:
        """Initialize the thermostat."""
        super().__init__(coordinator)
        self._device_key = device_key
        self._device_info = device_info
        self._attr_unique_id = f"{DOMAIN}_{device_key}"
        # 구성요소 이름 설정 (Thermostat 1, Thermostat 2 형식)
        parts = device_key.split("_")
        if len(parts) >= 2:
            room_num = parts[1]
            self._attr_name = f"Thermostat {room_num}"
        else:
            self._attr_name = device_info.get("name", f"Thermostat {device_info['device_id']}")
        
        # Set capabilities
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE |
            ClimateEntityFeature.TURN_ON |
            ClimateEntityFeature.TURN_OFF
        )
        
        # Temperature settings
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_min_temp = 5
        self._attr_max_temp = 40
        self._attr_target_temperature_step = 1
        
        # HVAC modes
        self._attr_hvac_modes = [
            HVACMode.OFF,
            HVACMode.HEAT,
            HVACMode.COOL,
            HVACMode.AUTO,
        ]
        
        # Device info는 base class에서 처리하도록 함
        self._attr_device_info = coordinator.get_device_info(device_key)

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        device = self.coordinator.devices.get(self._device_key, {})
        state = device.get("state", {})
        return state.get("current_temperature")

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        device = self.coordinator.devices.get(self._device_key, {})
        state = device.get("state", {})
        return state.get("target_temperature")

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        device = self.coordinator.devices.get(self._device_key, {})
        state = device.get("state", {})
        mode = state.get("mode", 0)
        
        # Map device mode to HVAC mode
        mode_map = {
            0: HVACMode.OFF,
            1: HVACMode.HEAT,
            2: HVACMode.COOL,
            3: HVACMode.AUTO,
        }
        return mode_map.get(mode, HVACMode.OFF)

    @property
    def hvac_action(self) -> Optional[HVACAction]:
        """Return the current running hvac operation."""
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        
        current = self.current_temperature
        target = self.target_temperature
        
        if current and target:
            if current < target:
                return HVACAction.HEATING
            elif current > target:
                return HVACAction.COOLING
            else:
                return HVACAction.IDLE
        
        return HVACAction.IDLE

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        
        await self.coordinator.send_command(
            "thermostat",
            self._device_info["device_id"],
            "target",
            int(temperature)
        )
        
        # Update local state immediately
        if self._device_key in self.coordinator.devices:
            self.coordinator.devices[self._device_key]["state"]["target_temperature"] = temperature
        
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        # Map HVAC mode to device mode
        mode_map = {
            HVACMode.OFF: 0,
            HVACMode.HEAT: 1,
            HVACMode.COOL: 2,
            HVACMode.AUTO: 3,
        }
        
        device_mode = mode_map.get(hvac_mode, 0)
        
        await self.coordinator.send_command(
            "thermostat",
            self._device_info["device_id"],
            "mode",
            device_mode
        )
        
        # Update local state immediately
        if self._device_key in self.coordinator.devices:
            self.coordinator.devices[self._device_key]["state"]["mode"] = device_mode
        
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn on the thermostat."""
        await self.async_set_hvac_mode(HVACMode.AUTO)

    async def async_turn_off(self) -> None:
        """Turn off the thermostat."""
        await self.async_set_hvac_mode(HVACMode.OFF)

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
