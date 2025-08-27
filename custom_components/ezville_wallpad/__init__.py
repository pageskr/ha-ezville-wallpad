"""Ezville Wallpad integration for Home Assistant."""
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    DOMAIN,
    CONF_CONNECTION_TYPE,
    CONF_SERIAL_PORT,
    CONF_HOST,
    CONF_PORT,
    CONF_MQTT_BROKER,
    CONF_MQTT_PORT,
    CONF_MQTT_USERNAME,
    CONF_MQTT_PASSWORD,
    CONF_MQTT_TOPIC_RECV,
    CONF_MQTT_TOPIC_SEND,
    CONF_MQTT_QOS,
    CONF_MQTT_STATE_SUFFIX,
    CONF_MQTT_COMMAND_SUFFIX,
    CONNECTION_TYPE_SERIAL,
    CONNECTION_TYPE_SOCKET,
    CONNECTION_TYPE_MQTT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_MQTT_QOS,
    DEFAULT_MQTT_STATE_SUFFIX,
    DEFAULT_MQTT_COMMAND_SUFFIX,
)
from .coordinator import EzvilleWallpadCoordinator

_LOGGER = logging.getLogger("custom_components.ezville_wallpad")

# Global logging settings
LOGGING_ENABLED = False
LOGGING_DEVICE_TYPES = []


def _setup_file_logging(hass: HomeAssistant):
    """Set up file logging handler."""
    import os
    from logging.handlers import TimedRotatingFileHandler
    
    # Create logs directory
    log_dir = os.path.join(hass.config.config_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # Create file handler
    log_file = os.path.join(log_dir, "ezville_wallpad.log")
    file_handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=7
    )
    
    # Get the root logger's level to follow Home Assistant's log level
    root_logger = logging.getLogger()
    file_handler.setLevel(root_logger.level)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    
    # Get all loggers for this integration
    loggers_to_setup = [
        "custom_components.ezville_wallpad",
        "custom_components.ezville_wallpad.coordinator",
        "custom_components.ezville_wallpad.sensor",
        "custom_components.ezville_wallpad.rs485_client"
    ]
    
    for logger_name in loggers_to_setup:
        logger = logging.getLogger(logger_name)
        # Remove existing file handlers to avoid duplicates
        for handler in logger.handlers[:]:
            if isinstance(handler, TimedRotatingFileHandler):
                logger.removeHandler(handler)
        
        # Add file handler
        logger.addHandler(file_handler)
        # Don't set propagate to False, let it follow HA's logging structure
    
    _LOGGER.info("File logging configured at: %s with level %s", log_file, logging.getLevelName(file_handler.level))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ezville Wallpad from a config entry."""
    # Set global logging settings
    global LOGGING_ENABLED, LOGGING_DEVICE_TYPES
    LOGGING_ENABLED = entry.options.get("enable_file_logging", False)
    LOGGING_DEVICE_TYPES = entry.options.get("logging_device_types", [])
    
    if LOGGING_ENABLED:
        _LOGGER.info("Starting Ezville Wallpad integration setup with file logging enabled")
        _LOGGER.info("Logging device types: %s", LOGGING_DEVICE_TYPES)
        
        # Setup file logging - do it in executor to avoid blocking
        await hass.async_add_executor_job(_setup_file_logging, hass)
    else:
        _LOGGER.info("Starting Ezville Wallpad integration setup")
    
    # Store entry data
    hass.data.setdefault(DOMAIN, {})
    
    # Extract configuration
    connection_type = entry.data[CONF_CONNECTION_TYPE]
    
    # Create coordinator based on connection type
    if connection_type == CONNECTION_TYPE_SERIAL:
        coordinator = EzvilleWallpadCoordinator(
            hass=hass,
            config_entry=entry,
            connection_type=connection_type,
            serial_port=entry.data[CONF_SERIAL_PORT],
            update_interval=timedelta(seconds=entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)),
        )
    elif connection_type == CONNECTION_TYPE_SOCKET:
        coordinator = EzvilleWallpadCoordinator(
            hass=hass,
            config_entry=entry,
            connection_type=connection_type,
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
            update_interval=timedelta(seconds=entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)),
        )
    elif connection_type == CONNECTION_TYPE_MQTT:
        # MQTT is event-driven, no need for regular polling
        coordinator = EzvilleWallpadCoordinator(
            hass=hass,
            config_entry=entry,
            connection_type=connection_type,
            mqtt_broker=entry.data[CONF_MQTT_BROKER],
            mqtt_port=entry.data[CONF_MQTT_PORT],
            mqtt_username=entry.data.get(CONF_MQTT_USERNAME),
            mqtt_password=entry.data.get(CONF_MQTT_PASSWORD),
            mqtt_topic_recv=entry.data.get(CONF_MQTT_TOPIC_RECV),
            mqtt_topic_send=entry.data.get(CONF_MQTT_TOPIC_SEND),
            mqtt_state_suffix=entry.data.get(CONF_MQTT_STATE_SUFFIX, DEFAULT_MQTT_STATE_SUFFIX),
            mqtt_command_suffix=entry.data.get(CONF_MQTT_COMMAND_SUFFIX, DEFAULT_MQTT_COMMAND_SUFFIX),
            mqtt_qos=entry.data.get(CONF_MQTT_QOS, DEFAULT_MQTT_QOS),
        )
    else:
        _LOGGER.error("Invalid connection type: %s", connection_type)
        return False
    
    # Store coordinator
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Perform initial connection
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.error("Failed to connect: %s", err)
        raise ConfigEntryNotReady from err
    
    # Get platforms to load
    platforms_to_load = coordinator.get_platforms_to_load()
    
    if platforms_to_load:
        _LOGGER.info("Loading platforms: %s", platforms_to_load)
        # Mark as loaded to prevent duplicate loading
        coordinator._platform_loaded.update(platforms_to_load)
        
        # Load platforms sequentially to avoid race conditions
        for platform in platforms_to_load:
            try:
                await hass.config_entries.async_forward_entry_setup(entry, platform)
                _LOGGER.info("Successfully loaded platform: %s", platform)
            except Exception as err:
                _LOGGER.error("Failed to load platform %s: %s", platform, err)
    else:
        _LOGGER.warning("No platforms to load - check capabilities and devices")

    # Setup options update listener
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    
    # Register services
    await async_setup_services(hass, coordinator)

    _LOGGER.info("Ezville Wallpad integration setup complete with %d devices", 
                len(coordinator.devices))
    return True


async def async_setup_services(hass: HomeAssistant, coordinator: EzvilleWallpadCoordinator):
    """Set up services for Ezville Wallpad."""
    import voluptuous as vol
    import homeassistant.helpers.config_validation as cv
    
    async def send_raw_command(call):
        """Handle send raw command service."""
        device_id = call.data.get("device_id")
        command = call.data.get("command") 
        data = call.data.get("data", "0x00")
        
        _LOGGER.debug("Service call: send_raw_command - device_id=%s, command=%s, data=%s",
                     device_id, command, data)
        
        try:
            # Convert hex strings to integers
            device_id_int = int(device_id, 16) if isinstance(device_id, str) else device_id
            command_int = int(command, 16) if isinstance(command, str) else command
            data_int = int(data, 16) if isinstance(data, str) else data
            
            # Create raw packet
            packet = bytearray([0xF7, device_id_int, 0x01, command_int, 0x01, data_int, 0x00, 0x00])
            
            # Generate checksum
            checksum = 0
            for b in packet[:-2]:
                checksum ^= b
            add = sum(packet[:-2]) & 0xFF
            packet[-2] = checksum
            packet[-1] = add
            
            # Send via coordinator
            if coordinator.client._conn:
                await hass.async_add_executor_job(
                    coordinator.client._conn.send, bytes(packet)
                )
                _LOGGER.info("Raw command sent: %s", packet.hex())
            else:
                _LOGGER.error("Connection not established")
            
        except Exception as err:
            _LOGGER.error("Failed to send raw command: %s", err)
    
    async def dump_packets(call):
        """Handle dump packets service.""" 
        duration = call.data.get("duration", 30)
        _LOGGER.info("Starting packet dump for %d seconds", duration)
        coordinator.client.dump_time = duration
        await coordinator.client._dump_packets()
    
    async def restart_connection(call):
        """Handle restart connection service."""
        _LOGGER.info("Restarting connection...")
        await hass.async_add_executor_job(coordinator.client.close)
        await coordinator.client.async_connect()
        _LOGGER.info("Connection restarted")
    
    async def test_device(call):
        """Handle test device service."""
        device_type = call.data.get("device_type")
        _LOGGER.info("Testing device type: %s", device_type)
        # Send a state query for the device
        if device_type in coordinator.capabilities:
            # This would send a state query - implementation depends on device type
            pass
    
    async def list_devices(call):
        """List all discovered devices."""
        devices_info = []
        for device_key, device_info in coordinator.devices.items():
            devices_info.append({
                "key": device_key,
                "type": device_info["device_type"],
                "id": device_info["device_id"],
                "name": device_info["name"],
                "state": device_info["state"]
            })
        _LOGGER.info("Current devices: %s", devices_info)
        return {"devices": devices_info}
    
    # Register services only once
    if not hass.services.has_service(DOMAIN, "send_raw_command"):
        hass.services.async_register(
            DOMAIN, 
            "send_raw_command",
            send_raw_command,
            schema=vol.Schema({
                vol.Required("device_id"): str,
                vol.Required("command"): str,
                vol.Optional("data", default="0x00"): str,
            })
        )
        _LOGGER.debug("Registered service: send_raw_command")
    
    if not hass.services.has_service(DOMAIN, "dump_packets"):
        hass.services.async_register(
            DOMAIN,
            "dump_packets", 
            dump_packets,
            schema=vol.Schema({
                vol.Required("duration"): vol.All(int, vol.Range(min=1, max=300)),
            })
        )
        _LOGGER.debug("Registered service: dump_packets")
    
    if not hass.services.has_service(DOMAIN, "restart_connection"):
        hass.services.async_register(DOMAIN, "restart_connection", restart_connection)
        _LOGGER.debug("Registered service: restart_connection")
    
    if not hass.services.has_service(DOMAIN, "test_device"):
        hass.services.async_register(
            DOMAIN,
            "test_device",
            test_device,
            schema=vol.Schema({
                vol.Required("device_type"): vol.In([
                    "light", "plug", "thermostat", "fan", "gas", 
                    "energy", "elevator", "doorbell"
                ]),
            })
        )
        _LOGGER.debug("Registered service: test_device")
    
    if not hass.services.has_service(DOMAIN, "list_devices"):
        hass.services.async_register(
            DOMAIN,
            "list_devices",
            list_devices,
        )
        _LOGGER.debug("Registered service: list_devices")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Ezville Wallpad integration")
    
    # Get coordinator
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Get loaded platforms
    loaded_platforms = list(coordinator._platform_loaded)
    
    _LOGGER.debug("Unloading platforms: %s", loaded_platforms)
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, loaded_platforms)
    
    if unload_ok:
        # Stop coordinator
        await coordinator.async_shutdown()
        
        # Remove entry from data
        hass.data[DOMAIN].pop(entry.entry_id)
        
        # Remove services if no other instances
        if not hass.data[DOMAIN]:
            _LOGGER.debug("Removing services")
            hass.services.async_remove(DOMAIN, "send_raw_command")
            hass.services.async_remove(DOMAIN, "dump_packets")
            hass.services.async_remove(DOMAIN, "restart_connection")
            hass.services.async_remove(DOMAIN, "test_device")
            hass.services.async_remove(DOMAIN, "list_devices")

    _LOGGER.info("Unload complete: %s", unload_ok)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    _LOGGER.info("Reloading config entry")
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    # Update global logging settings
    global LOGGING_ENABLED, LOGGING_DEVICE_TYPES
    LOGGING_ENABLED = entry.options.get("enable_file_logging", False)
    LOGGING_DEVICE_TYPES = entry.options.get("logging_device_types", [])
    
    if LOGGING_ENABLED:
        _LOGGER.info("Options updated, reloading entry")
    await hass.config_entries.async_reload(entry.entry_id)
