"""Config flow for Ezville Wallpad integration."""
import logging
from typing import Any, Dict, Optional
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

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
    DEFAULT_PORT,
    DEFAULT_MQTT_PORT,
    DEFAULT_MQTT_TOPIC_RECV,
    DEFAULT_MQTT_TOPIC_SEND,
    DEFAULT_MQTT_QOS,
    DEFAULT_MQTT_STATE_SUFFIX,
    DEFAULT_MQTT_COMMAND_SUFFIX,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_MAX_RETRY,
)
from .rs485_client import EzvilleRS485Client

_LOGGER = logging.getLogger(__name__)


class EzvilleWallpadConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ezville Wallpad."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the config flow."""
        self._connection_type = None
        self._errors = {}

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            self._connection_type = user_input[CONF_CONNECTION_TYPE]
            
            if self._connection_type == CONNECTION_TYPE_SERIAL:
                return await self.async_step_serial()
            elif self._connection_type == CONNECTION_TYPE_SOCKET:
                return await self.async_step_socket()
            elif self._connection_type == CONNECTION_TYPE_MQTT:
                return await self.async_step_mqtt()

        data_schema = vol.Schema({
            vol.Required(CONF_CONNECTION_TYPE, default=CONNECTION_TYPE_SERIAL): vol.In([
                CONNECTION_TYPE_SERIAL,
                CONNECTION_TYPE_SOCKET,
                CONNECTION_TYPE_MQTT,
            ]),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=self._errors,
        )

    async def async_step_serial(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle serial connection setup."""
        if user_input is not None:
            # Test serial connection
            serial_port = user_input[CONF_SERIAL_PORT]
            
            try:
                _LOGGER.debug("Testing serial connection to %s", serial_port)
                client = EzvilleRS485Client(
                    connection_type=CONNECTION_TYPE_SERIAL,
                    serial_port=serial_port
                )
                result = await self.hass.async_add_executor_job(client.test_connection)
                await self.hass.async_add_executor_job(client.close)
                
                if not result:
                    raise Exception("Connection test failed")
                
                _LOGGER.info("Serial connection test successful")
                
                # Create entry with all configuration
                return self.async_create_entry(
                    title=f"Ezville Wallpad ({serial_port})",
                    data={
                        CONF_CONNECTION_TYPE: CONNECTION_TYPE_SERIAL,
                        CONF_SERIAL_PORT: serial_port,
                    },
                    options={
                        "scan_interval": user_input.get("scan_interval", DEFAULT_SCAN_INTERVAL),
                        "max_retry": user_input.get("max_retry", DEFAULT_MAX_RETRY),
                        "dump_time": user_input.get("dump_time", 0),
                        "log_to_file": user_input.get("log_to_file", False),
                        "capabilities": user_input.get("capabilities", [
                            "light", "plug", "thermostat", "fan", "gas", 
                            "energy", "elevator", "doorbell"
                        ]),
                    },
                )
                
            except Exception as err:
                _LOGGER.error("Failed to connect to serial port %s: %s", serial_port, err)
                self._errors["base"] = "cannot_connect"

        data_schema = vol.Schema({
            vol.Required(CONF_SERIAL_PORT, default="/dev/ttyUSB0"): str,
            vol.Optional("scan_interval", default=DEFAULT_SCAN_INTERVAL): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=300)
            ),
            vol.Optional("max_retry", default=DEFAULT_MAX_RETRY): vol.All(
                vol.Coerce(int), vol.Range(min=3, max=60)
            ),
            vol.Optional("dump_time", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=60)
            ),
            vol.Optional("log_to_file", default=False): bool,
            vol.Optional("capabilities", default=[
                "light", "plug", "thermostat", "fan", "gas", 
                "energy", "elevator", "doorbell"
            ]): cv.multi_select([
                "light", "plug", "thermostat", "fan", "gas", 
                "energy", "elevator", "doorbell"
            ]),
        })

        return self.async_show_form(
            step_id="serial",
            data_schema=data_schema,
            errors=self._errors,
        )

    async def async_step_socket(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle socket connection setup."""
        if user_input is not None:
            # Test socket connection
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            
            try:
                _LOGGER.debug("Testing socket connection to %s:%s", host, port)
                client = EzvilleRS485Client(
                    connection_type=CONNECTION_TYPE_SOCKET,
                    host=host,
                    port=port
                )
                result = await self.hass.async_add_executor_job(client.test_connection)
                await self.hass.async_add_executor_job(client.close)
                
                if not result:
                    raise Exception("Connection test failed")
                
                _LOGGER.info("Socket connection test successful")
                
                # Create entry with all configuration
                return self.async_create_entry(
                    title=f"Ezville Wallpad ({host}:{port})",
                    data={
                        CONF_CONNECTION_TYPE: CONNECTION_TYPE_SOCKET,
                        CONF_HOST: host,
                        CONF_PORT: port,
                    },
                    options={
                        "scan_interval": user_input.get("scan_interval", DEFAULT_SCAN_INTERVAL),
                        "max_retry": user_input.get("max_retry", DEFAULT_MAX_RETRY),
                        "dump_time": user_input.get("dump_time", 0),
                        "log_to_file": user_input.get("log_to_file", False),
                        "capabilities": user_input.get("capabilities", [
                            "light", "plug", "thermostat", "fan", "gas", 
                            "energy", "elevator", "doorbell"
                        ]),
                    },
                )
                
            except Exception as err:
                _LOGGER.error("Failed to connect to %s:%s: %s", host, port, err)
                self._errors["base"] = "cannot_connect"

        data_schema = vol.Schema({
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
            vol.Optional("scan_interval", default=DEFAULT_SCAN_INTERVAL): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=300)
            ),
            vol.Optional("max_retry", default=DEFAULT_MAX_RETRY): vol.All(
                vol.Coerce(int), vol.Range(min=3, max=60)
            ),
            vol.Optional("dump_time", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=60)
            ),
            vol.Optional("log_to_file", default=False): bool,
            vol.Optional("capabilities", default=[
                "light", "plug", "thermostat", "fan", "gas", 
                "energy", "elevator", "doorbell"
            ]): cv.multi_select([
                "light", "plug", "thermostat", "fan", "gas", 
                "energy", "elevator", "doorbell"
            ]),
        })

        return self.async_show_form(
            step_id="socket",
            data_schema=data_schema,
            errors=self._errors,
        )

    async def async_step_mqtt(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle MQTT connection setup."""
        if user_input is not None:
            # Test MQTT connection
            broker = user_input[CONF_MQTT_BROKER]
            mqtt_port = user_input[CONF_MQTT_PORT]
            username = user_input.get(CONF_MQTT_USERNAME)
            password = user_input.get(CONF_MQTT_PASSWORD)
            topic_recv = user_input.get(CONF_MQTT_TOPIC_RECV, DEFAULT_MQTT_TOPIC_RECV)
            topic_send = user_input.get(CONF_MQTT_TOPIC_SEND, DEFAULT_MQTT_TOPIC_SEND)
            state_suffix = user_input.get(CONF_MQTT_STATE_SUFFIX, DEFAULT_MQTT_STATE_SUFFIX)
            command_suffix = user_input.get(CONF_MQTT_COMMAND_SUFFIX, DEFAULT_MQTT_COMMAND_SUFFIX)
            qos = user_input.get(CONF_MQTT_QOS, DEFAULT_MQTT_QOS)
            
            try:
                _LOGGER.debug("Testing MQTT connection to %s:%s", broker, mqtt_port)
                client = EzvilleRS485Client(
                    connection_type=CONNECTION_TYPE_MQTT,
                    mqtt_broker=broker,
                    mqtt_port=mqtt_port,
                    mqtt_username=username,
                    mqtt_password=password,
                    mqtt_topic_recv=topic_recv,
                    mqtt_topic_send=topic_send,
                    mqtt_state_suffix=state_suffix,
                    mqtt_command_suffix=command_suffix,
                    mqtt_qos=qos
                )
                result = await self.hass.async_add_executor_job(client.test_connection)
                await self.hass.async_add_executor_job(client.close)
                
                if not result:
                    raise Exception("Connection test failed")
                
                _LOGGER.info("MQTT connection test successful")
                
                # Create entry with all configuration
                return self.async_create_entry(
                    title=f"Ezville Wallpad (MQTT: {broker})",
                    data={
                        CONF_CONNECTION_TYPE: CONNECTION_TYPE_MQTT,
                        CONF_MQTT_BROKER: broker,
                        CONF_MQTT_PORT: mqtt_port,
                        CONF_MQTT_USERNAME: username,
                        CONF_MQTT_PASSWORD: password,
                        CONF_MQTT_TOPIC_RECV: topic_recv,
                        CONF_MQTT_TOPIC_SEND: topic_send,
                        CONF_MQTT_STATE_SUFFIX: state_suffix,
                        CONF_MQTT_COMMAND_SUFFIX: command_suffix,
                        CONF_MQTT_QOS: qos,
                    },
                    options={
                        "log_to_file": user_input.get("log_to_file", False),
                        "capabilities": user_input.get("capabilities", [
                            "light", "plug", "thermostat", "fan", "gas", 
                            "energy", "elevator", "doorbell"
                        ]),
                    },
                )
                
            except Exception as err:
                _LOGGER.error("Failed to connect to MQTT broker %s:%s: %s", broker, mqtt_port, err)
                self._errors["base"] = "cannot_connect"

        data_schema = vol.Schema({
            vol.Required(CONF_MQTT_BROKER): str,
            vol.Required(CONF_MQTT_PORT, default=DEFAULT_MQTT_PORT): cv.port,
            vol.Optional(CONF_MQTT_USERNAME): str,
            vol.Optional(CONF_MQTT_PASSWORD): str,
            vol.Optional(CONF_MQTT_TOPIC_RECV, default=DEFAULT_MQTT_TOPIC_RECV): str,
            vol.Optional(CONF_MQTT_TOPIC_SEND, default=DEFAULT_MQTT_TOPIC_SEND): str,
            vol.Optional(CONF_MQTT_STATE_SUFFIX, default=DEFAULT_MQTT_STATE_SUFFIX): str,
            vol.Optional(CONF_MQTT_COMMAND_SUFFIX, default=DEFAULT_MQTT_COMMAND_SUFFIX): str,
            vol.Optional(CONF_MQTT_QOS, default=DEFAULT_MQTT_QOS): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=2)
            ),
            vol.Optional("log_to_file", default=False): bool,
            vol.Optional("capabilities", default=[
                "light", "plug", "thermostat", "fan", "gas", 
                "energy", "elevator", "doorbell"
            ]): cv.multi_select([
                "light", "plug", "thermostat", "fan", "gas", 
                "energy", "elevator", "doorbell"
            ]),
        })

        return self.async_show_form(
            step_id="mqtt",
            data_schema=data_schema,
            errors=self._errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return EzvilleWallpadOptionsFlowHandler(config_entry)


class EzvilleWallpadOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Ezville Wallpad options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            _LOGGER.debug("Updating options: %s", user_input)
            return self.async_create_entry(title="", data=user_input)

        connection_type = self._config_entry.data.get(CONF_CONNECTION_TYPE)
        
        # Build schema based on connection type
        if connection_type == CONNECTION_TYPE_MQTT:
            # MQTT doesn't need scan_interval, max_retry, dump_time
            data_schema = vol.Schema({
                vol.Optional(
                    CONF_MQTT_TOPIC_RECV,
                    default=self._config_entry.data.get(CONF_MQTT_TOPIC_RECV, DEFAULT_MQTT_TOPIC_RECV),
                ): str,
                vol.Optional(
                    CONF_MQTT_TOPIC_SEND,
                    default=self._config_entry.data.get(CONF_MQTT_TOPIC_SEND, DEFAULT_MQTT_TOPIC_SEND),
                ): str,
                vol.Optional(
                    CONF_MQTT_STATE_SUFFIX,
                    default=self._config_entry.data.get(CONF_MQTT_STATE_SUFFIX, DEFAULT_MQTT_STATE_SUFFIX),
                ): str,
                vol.Optional(
                    CONF_MQTT_COMMAND_SUFFIX,
                    default=self._config_entry.data.get(CONF_MQTT_COMMAND_SUFFIX, DEFAULT_MQTT_COMMAND_SUFFIX),
                ): str,
                vol.Optional(
                    CONF_MQTT_QOS,
                    default=self._config_entry.data.get(CONF_MQTT_QOS, DEFAULT_MQTT_QOS),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=2)),
                vol.Optional(
                    "log_to_file",
                    default=self._config_entry.options.get("log_to_file", False),
                ): bool,
                vol.Optional(
                    "capabilities",
                    default=self._config_entry.options.get("capabilities", [
                        "light", "plug", "thermostat", "fan", "gas", 
                        "energy", "elevator", "doorbell"
                    ]),
                ): cv.multi_select([
                    "light", "plug", "thermostat", "fan", "gas", 
                    "energy", "elevator", "doorbell"
                ]),
            })
        else:
            # Serial and Socket need all options
            data_schema = vol.Schema({
                vol.Optional(
                    "scan_interval",
                    default=self._config_entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=300)),
                vol.Optional(
                    "max_retry",
                    default=self._config_entry.options.get("max_retry", DEFAULT_MAX_RETRY),
                ): vol.All(vol.Coerce(int), vol.Range(min=3, max=60)),
                vol.Optional(
                    "dump_time",
                    default=self._config_entry.options.get("dump_time", 0),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=60)),
                vol.Optional(
                    "log_to_file",
                    default=self._config_entry.options.get("log_to_file", False),
                ): bool,
                vol.Optional(
                    "capabilities",
                    default=self._config_entry.options.get("capabilities", [
                        "light", "plug", "thermostat", "fan", "gas", 
                        "energy", "elevator", "doorbell"
                    ]),
                ): cv.multi_select([
                    "light", "plug", "thermostat", "fan", "gas", 
                    "energy", "elevator", "doorbell"
                ]),
            })

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
        )