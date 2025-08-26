"""Base device class for Ezville Wallpad."""
from typing import Any, Dict, Optional

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL, DOCUMENTATION_URL
from .coordinator import EzvilleWallpadCoordinator


class EzvilleWallpadDevice(CoordinatorEntity):
    """Base class for Ezville Wallpad devices."""

    def __init__(
        self,
        coordinator: EzvilleWallpadCoordinator,
        device_key: str,
        unique_id: str,
        name: str,
    ):
        """Initialize the device."""
        super().__init__(coordinator)
        
        self._device_key = device_key
        self._attr_unique_id = unique_id
        self._attr_name = name
        
        # Extract device ID from device key
        parts = device_key.split("_")
        # For unknown devices, parts[1] is the signature (hex string), not an integer
        if device_key.startswith("unknown_"):
            self._device_id = parts[1] if len(parts) > 1 else "00000000"
        else:
            try:
                self._device_id = int(parts[1]) if len(parts) > 1 else 0
            except ValueError:
                # If conversion fails, keep as string
                self._device_id = parts[1] if len(parts) > 1 else "0"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        device_type = self._device_key.split("_")[0]
        parts = self._device_key.split("_")
        
        # 기기별 이름 생성 및 식별자 로직
        if device_type == "light":
            # light_1_2 -> Light 1 기기로 그룹핑
            room_id = parts[1] if len(parts) > 1 else "1"
            device_name = f"Light {room_id}"
            device_identifier = f"{device_type}_{room_id}"
        elif device_type == "plug":
            # plug_1_2 -> Plug 1 기기로 그룹핑
            room_id = parts[1] if len(parts) > 1 else "1"
            device_name = f"Plug {room_id}"
            device_identifier = f"{device_type}_{room_id}"
        elif device_type == "thermostat":
            # 모든 thermostat을 하나의 기기로
            device_name = "Thermostat"
            device_identifier = device_type
        elif device_type == "gas":
            device_name = "Gas"
            device_identifier = self._device_key
        elif device_type == "fan":
            device_name = "Ventilation"
            device_identifier = self._device_key
        elif device_type == "energy":
            device_name = "Energy"
            device_identifier = self._device_key
        elif device_type == "elevator":
            device_name = "Elevator"
            device_identifier = self._device_key
        elif device_type == "doorbell":
            device_name = "Doorbell"
            device_identifier = self._device_key
        elif device_type == "unknown":
            # All unknown devices group under single Unknown device
            device_name = "Unknown"
            device_identifier = "unknown"
        else:
            device_name = f"Ezville Wallpad {self._device_key}"
            device_identifier = self._device_key
        
        return DeviceInfo(
            identifiers={(DOMAIN, device_identifier)},
            name=device_name,
            manufacturer=MANUFACTURER,
            model=MODEL,
            hw_version="1.0",
            sw_version="1.0.0",
            configuration_url=DOCUMENTATION_URL,
            suggested_area=self._get_suggested_area(device_type),
        )

    def _get_device_display_name(self, device_type: str) -> str:
        """Get display name for device type."""
        display_names = {
            "light": "Light",
            "plug": "Plug",
            "thermostat": "Thermostat",
            "fan": "Ventilation",
            "gas": "Gas",
            "energy": "Energy",
            "elevator": "Elevator",
            "doorbell": "Doorbell",
            "unknown": "Unknown",
        }
        return display_names.get(device_type, device_type.title())
    
    def _get_suggested_area(self, device_type: str) -> Optional[str]:
        """Get suggested area for device type."""
        area_mapping = {
            "light": "거실",
            "plug": "거실", 
            "thermostat": "거실",
            "fan": "욕실",
            "gas": "주방",
            "energy": None,
            "elevator": "현관",
            "doorbell": "현관",
            "unknown": None,
        }
        return area_mapping.get(device_type)

    @property 
    def icon(self) -> str:
        """Return the icon for the entity."""
        # Use LG air conditioner icon or generic LG icon
        device_type = self._device_key.split("_")[0]
        icons = {
            "light": "mdi:lightbulb",
            "plug": "mdi:power-socket-de", 
            "thermostat": "mdi:air-conditioner",  # LG AC style icon
            "fan": "mdi:fan",
            "gas": "mdi:gas-cylinder",
            "energy": "mdi:flash",
            "elevator": "mdi:elevator",
            "doorbell": "mdi:doorbell",
            "unknown": "mdi:help-circle",
        }
        return icons.get(device_type, "mdi:home-automation")  # LG brand style fallback

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self._device_key in self.coordinator.data

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        
        # Register callback for real-time updates
        self.coordinator.register_entity_callback(self._device_key, self._handle_state_update)

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        
        # Unregister callback
        self.coordinator.unregister_entity_callback(self._device_key, self._handle_state_update)

    def _handle_state_update(self, state: Dict[str, Any]) -> None:
        """Handle state update from coordinator."""
        # This method is not used - actual entities have their own update handlers
        pass