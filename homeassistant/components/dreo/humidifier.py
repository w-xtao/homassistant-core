"""Support for Dreo humidifier entities."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.humidifier import (
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DreoConfigEntry
from .const import (
    DreoDeviceType,
    DreoDirective,
    DreoEntityConfigSpec,
    DreoErrorCode,
    DreoFeatureSpec,
)
from .coordinator import (
    DreoDataUpdateCoordinator,
    DreoHecDeviceData,
    DreoHumidifierDeviceData,
)
from .entity import DreoEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DreoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Dreo humidifier entities from a config entry."""

    @callback
    def async_add_humidifier_entities() -> None:
        """Add humidifier entities."""
        humidifiers: list[DreoHecHumidifier | DreoHumidifier] = []

        for device in config_entry.runtime_data.devices:
            device_type = device.get("deviceType")
            if device_type not in [DreoDeviceType.HEC, DreoDeviceType.HUMIDIFIER]:
                continue

            device_id = device.get("deviceSn")
            if not device_id:
                continue

            device_config = device.get(DreoEntityConfigSpec.TOP_CONFIG, {})
            entity_supports = device_config.get("entitySupports", [])
            device_model = device.get("model")

            _LOGGER.debug(
                "Device %s config %s Platform.HUMIDIFIER value: %s",
                device_model,
                device_config,
                Platform.HUMIDIFIER,
            )

            if Platform.HUMIDIFIER not in entity_supports:
                _LOGGER.warning(
                    "No humidifier entity support for model %s (entitySupports: %s)",
                    device_model,
                    entity_supports,
                )
                continue

            coordinator = config_entry.runtime_data.coordinators.get(device_id)
            if not coordinator:
                _LOGGER.error("Coordinator not found for device %s", device_id)
                continue

            if device_type == DreoDeviceType.HEC:
                humidifier_entity: DreoHecHumidifier | DreoHumidifier = (
                    DreoHecHumidifier(device, coordinator)
                )
                humidifiers.append(humidifier_entity)
            elif device_type == DreoDeviceType.HUMIDIFIER:
                humidifier_entity = DreoHumidifier(device, coordinator)
                humidifiers.append(humidifier_entity)

        if humidifiers:
            async_add_entities(humidifiers)

    async_add_humidifier_entities()


class DreoHecHumidifier(DreoEntity, HumidifierEntity):
    """Dreo HEC (Hybrid Evaporative Cooler) humidifier entity."""

    _attr_supported_features = HumidifierEntityFeature.MODES
    _attr_is_on = False
    _attr_mode: str | None = None
    _attr_current_humidity: int | None = None
    _attr_target_humidity: int | None = None
    _attr_available_modes: list[str] = []

    def __init__(
        self,
        device: dict[str, Any],
        coordinator: DreoDataUpdateCoordinator,
    ) -> None:
        """Initialize the Dreo HEC humidifier."""
        super().__init__(device, coordinator, "humidifier", "Humidifier")

        model_config = coordinator.model_config

        humidity_range = model_config.get(DreoFeatureSpec.HUMIDITY_RANGE)
        if humidity_range and len(humidity_range) >= 2:
            self._attr_min_humidity = int(humidity_range[0])
            self._attr_max_humidity = int(humidity_range[1])

        self._attr_available_modes = (
            model_config.get(DreoFeatureSpec.PRESET_MODES) or []
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attributes()
        super()._handle_coordinator_update()

    def _update_attributes(self) -> None:
        """Update attributes from coordinator data."""
        if not self.coordinator.data:
            return

        if not isinstance(self.coordinator.data, DreoHecDeviceData):
            return

        hec_data = self.coordinator.data
        self._attr_available = hec_data.available
        self._attr_is_on = hec_data.is_on

        if hec_data.target_humidity is not None:
            self._attr_target_humidity = int(hec_data.target_humidity)

        if (
            hec_data.mode
            and self._attr_available_modes
            and hec_data.mode in self._attr_available_modes
        ):
            self._attr_mode = hec_data.mode
        else:
            self._attr_mode = "Normal"

    @property
    def is_on(self) -> bool:
        """Return True if the humidifier is on."""
        return self._attr_is_on

    @property
    def mode(self) -> str | None:
        """Return the current mode."""
        return self._attr_mode

    @property
    def target_humidity(self) -> int | None:
        """Return the target humidity."""
        return self._attr_target_humidity

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the humidifier on."""
        await self.async_send_command_and_update(
            DreoErrorCode.TURN_ON_FAILED, power_switch=True
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the humidifier off."""
        await self.async_send_command_and_update(
            DreoErrorCode.TURN_OFF_FAILED, power_switch=False
        )

    async def async_set_humidity(self, humidity: int) -> None:
        """Set the target humidity."""
        if not (self._attr_min_humidity <= humidity <= self._attr_max_humidity):
            _LOGGER.error(
                "Humidity %d is out of range [%d-%d]",
                humidity,
                self._attr_min_humidity,
                self._attr_max_humidity,
            )
            return

        command_params: dict[str, Any] = {}

        if not self.is_on:
            command_params[DreoDirective.POWER_SWITCH] = True

        command_params[DreoDirective.HUMIDITY] = int(humidity)

        await self.async_send_command_and_update(
            DreoErrorCode.SET_HEC_HUMIDITY_FAILED, **command_params
        )

    async def async_set_mode(self, mode: str) -> None:
        """Set the mode of the humidifier."""
        if not self._attr_available_modes or mode not in self._attr_available_modes:
            _LOGGER.error("Mode %s is not available", mode)
            return

        command_params: dict[str, Any] = {}

        if not self.is_on:
            command_params[DreoDirective.POWER_SWITCH] = True

        command_params[DreoDirective.MODE] = mode.capitalize()

        await self.async_send_command_and_update(
            DreoErrorCode.SET_HUMIDIFIER_MODE_FAILED, **command_params
        )


class DreoHumidifier(DreoEntity, HumidifierEntity):
    """Dreo Humidifier entity for dedicated humidifier devices like HHM001S."""

    _attr_supported_features = HumidifierEntityFeature.MODES
    _attr_is_on = False
    _attr_mode: str | None = None
    _attr_current_humidity: int | None = None
    _attr_target_humidity: int | None = None
    _attr_available_modes: list[str] = []
    _attr_directive_graph: dict[str, Any] = {}

    def __init__(
        self,
        device: dict[str, Any],
        coordinator: DreoDataUpdateCoordinator,
    ) -> None:
        """Initialize the Dreo humidifier."""
        super().__init__(device, coordinator, "humidifier", "Humidifier")

        model_config = coordinator.model_config
        humidifier_config = model_config.get("humidifier_entity_config", {})

        # Set humidity range
        humidity_range = humidifier_config.get("humidity_range")
        if humidity_range and len(humidity_range) >= 2:
            self._attr_min_humidity = int(humidity_range[0])
            self._attr_max_humidity = int(humidity_range[1])
        else:
            self._attr_min_humidity = 30
            self._attr_max_humidity = 90

        humidity_mode_config = humidifier_config.get("humidity_mode_config", {})

        # Set available modes
        self._attr_available_modes = humidity_mode_config.get("preset_modes", [])
        self._attr_directive_graph = humidity_mode_config.get("directive_graph", {})

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attributes()
        super()._handle_coordinator_update()

    def _update_attributes(self) -> None:
        """Update attributes from coordinator data."""
        if not self.coordinator.data:
            return

        if not isinstance(self.coordinator.data, DreoHumidifierDeviceData):
            return

        humidifier_data = self.coordinator.data
        self._attr_available = humidifier_data.available
        self._attr_is_on = humidifier_data.is_on

        if humidifier_data.target_humidity is not None:
            self._attr_target_humidity = int(humidifier_data.target_humidity)

        if (
            humidifier_data.mode
            and self._attr_available_modes
            and humidifier_data.mode in self._attr_available_modes
        ):
            self._attr_mode = humidifier_data.mode
        elif self._attr_available_modes:
            self._attr_mode = self._attr_available_modes[0]
        else:
            self._attr_mode = "Manual"

    @property
    def is_on(self) -> bool:
        """Return True if the humidifier is on."""
        return self._attr_is_on

    @property
    def mode(self) -> str | None:
        """Return the current mode."""
        return self._attr_mode

    @property
    def target_humidity(self) -> int | None:
        """Return the target humidity."""
        return self._attr_target_humidity

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the humidifier on."""
        await self.async_send_command_and_update(
            DreoErrorCode.TURN_ON_FAILED, power_switch=True
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the humidifier off."""
        await self.async_send_command_and_update(
            DreoErrorCode.TURN_OFF_FAILED, power_switch=False
        )

    async def async_set_humidity(self, humidity: int) -> None:
        """Set the target humidity."""
        if not (self._attr_min_humidity <= humidity <= self._attr_max_humidity):
            _LOGGER.error(
                "Humidity %d is out of range [%d-%d]",
                humidity,
                self._attr_min_humidity,
                self._attr_max_humidity,
            )
            return

        command_params: dict[str, Any] = {}

        if not self.is_on:
            command_params[DreoDirective.POWER_SWITCH] = True

        current_mode = self.mode
        mode_graph = self._attr_directive_graph.get(current_mode or "", {})
        directive_name = mode_graph.get("name")
        if current_mode is not None and current_mode in mode_graph.get(
            "out_of_services", []
        ):
            _LOGGER.error("Mode %s is not support this function", self.mode)
            return

        if directive_name:
            command_params[directive_name] = int(humidity)

        await self.async_send_command_and_update(
            DreoErrorCode.SET_HEC_HUMIDITY_FAILED, **command_params
        )

    async def async_set_mode(self, mode: str) -> None:
        """Set the mode of the humidifier."""
        if not self._attr_available_modes or mode not in self._attr_available_modes:
            _LOGGER.error("Mode %s is not available", mode)
            return

        command_params: dict[str, Any] = {}

        if not self.is_on:
            command_params[DreoDirective.POWER_SWITCH] = True

        command_params[DreoDirective.MODE] = mode

        await self.async_send_command_and_update(
            DreoErrorCode.SET_HUMIDIFIER_MODE_FAILED, **command_params
        )
