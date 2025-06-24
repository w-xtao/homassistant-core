"""Support for Dreo fans."""

from __future__ import annotations

import logging
import math
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import percentage_to_ranged_value

from . import DreoConfigEntry
from .const import (
    CIR_FAN_DEVICE_TYPE,
    ERROR_SET_OSCILLATE_FAILED,
    ERROR_SET_PRESET_MODE_FAILED,
    ERROR_SET_SPEED_FAILED,
    ERROR_TURN_OFF_FAILED,
    ERROR_TURN_ON_FAILED,
    FAN_DEVICE_TYPE,
)
from .coordinator import DreoDataUpdateCoordinator
from .entity import DreoEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DreoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Fan from a config entry."""

    @callback
    def async_add_fan_devices() -> None:
        """Add fan devices."""
        new_fans: list[DreoFan | DreoCirculationFan] = []

        for device in config_entry.runtime_data.devices:
            device_type = device.get("deviceType")
            if device_type is None:
                continue

            # Only process fan-type devices
            if device_type not in [FAN_DEVICE_TYPE, CIR_FAN_DEVICE_TYPE]:
                continue

            device_id = device.get("deviceSn")
            if not device_id:
                continue

            coordinator = config_entry.runtime_data.coordinators.get(device_id)
            if not coordinator:
                _LOGGER.error("Coordinator not found for device %s", device_id)
                continue

            if device_type == FAN_DEVICE_TYPE:
                fan = DreoFan(device, coordinator)
                new_fans.append(fan)
            elif device_type == CIR_FAN_DEVICE_TYPE:
                circulation_fan = DreoCirculationFan(device, coordinator)
                new_fans.append(circulation_fan)

        if new_fans:
            async_add_entities(new_fans)

    async_add_fan_devices()


class DreoFan(DreoEntity, FanEntity):
    """Dreo fan."""

    _attr_supported_features = (
        FanEntityFeature.PRESET_MODE
        | FanEntityFeature.SET_SPEED
        | FanEntityFeature.OSCILLATE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_is_on = False
    _attr_percentage = 0
    _attr_preset_mode = None
    _attr_oscillating = None
    _low_high_range: tuple[int, int]

    def __init__(
        self,
        device: dict[str, Any],
        coordinator: DreoDataUpdateCoordinator,
    ) -> None:
        """Initialize the Dreo fan."""
        super().__init__(device, coordinator, "fan", None)

        model_config = coordinator.model_config
        speed_range = model_config.get("speed_range")

        if speed_range:
            self._low_high_range = tuple(speed_range)
        else:
            self._low_high_range = (1, 9)
        self._attr_preset_modes = model_config.get("preset_modes")

    @callback
    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        self._update_attributes()
        super()._handle_coordinator_update()

    def _update_attributes(self):
        """Update attributes from coordinator data."""
        if not self.coordinator.data:
            return

        fan_state_data = self.coordinator.data
        self._attr_available = fan_state_data.available

        if not fan_state_data.is_on:
            self._attr_percentage = 0
            self._attr_preset_mode = None
            self._attr_oscillating = None
        else:
            self._attr_preset_mode = fan_state_data.mode
            self._attr_oscillating = fan_state_data.oscillate
            self._attr_percentage = fan_state_data.speed_percentage

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the device on."""
        await self.async_execute_fan_common_command(
            ERROR_TURN_ON_FAILED, percentage=percentage, preset_mode=preset_mode
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.async_send_command_and_update(
            ERROR_TURN_OFF_FAILED, power_switch=False
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of fan."""
        await self.async_execute_fan_common_command(
            ERROR_SET_PRESET_MODE_FAILED, preset_mode=preset_mode
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of fan."""

        if percentage <= 0:
            await self.async_turn_off()
            return

        await self.async_execute_fan_common_command(
            ERROR_SET_SPEED_FAILED, percentage=percentage
        )

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set the oscillation of fan."""
        await self.async_execute_fan_common_command(
            ERROR_SET_OSCILLATE_FAILED, oscillate=oscillating
        )

    async def async_execute_fan_common_command(
        self,
        error_translation_key: str,
        percentage: int | None = None,
        preset_mode: str | None = None,
        oscillate: bool | None = None,
    ) -> None:
        """Execute fan command with common parameter handling."""

        command_params: dict[str, Any] = {}

        if not self.is_on:
            command_params["power_switch"] = True

        if percentage is not None and percentage > 0 and self._low_high_range:
            speed = math.ceil(
                percentage_to_ranged_value(self._low_high_range, percentage)
            )
            if speed is not None and speed > 0:
                command_params["speed"] = speed

        if preset_mode is not None:
            command_params["mode"] = preset_mode
        if oscillate is not None:
            command_params["oscillate"] = oscillate

        await self.async_send_command_and_update(
            error_translation_key, **command_params
        )


class DreoCirculationFan(DreoEntity, FanEntity):
    """Dreo circulation fan."""

    _attr_supported_features = (
        FanEntityFeature.PRESET_MODE
        | FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_is_on = False
    _attr_percentage = 0
    _attr_preset_mode = None
    _low_high_range: tuple[int, int]

    def __init__(
        self,
        device: dict[str, Any],
        coordinator: DreoDataUpdateCoordinator,
    ) -> None:
        """Initialize the Dreo circulation fan."""
        super().__init__(device, coordinator, CIR_FAN_DEVICE_TYPE, None)

        config = coordinator.model_config

        self._attr_preset_modes = config.get("preset_modes")

        self._select_options = config.get("selectOptions")

        speed_range = config.get("speed_range")
        if speed_range and len(speed_range) >= 2:
            self._low_high_range = tuple(speed_range)
        else:
            self._low_high_range = (1, 9)

    @callback
    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        self._update_attributes()
        super()._handle_coordinator_update()

    def _update_attributes(self):
        """Update attributes from coordinator data."""
        if not self.coordinator.data:
            return

        fan_state_data = self.coordinator.data
        self._attr_available = fan_state_data.available

        if not fan_state_data.is_on:
            self._attr_percentage = 0
            self._attr_preset_mode = None
            self._attr_oscillating = False
        else:
            self._attr_preset_mode = fan_state_data.mode
            self._attr_percentage = fan_state_data.speed_percentage

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the device on."""
        await self.async_execute_circulation_fan_command(
            ERROR_TURN_ON_FAILED, percentage=percentage, preset_mode=preset_mode
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.async_send_command_and_update(
            ERROR_TURN_OFF_FAILED, power_switch=False
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of circulation fan."""
        await self.async_execute_circulation_fan_command(
            ERROR_SET_PRESET_MODE_FAILED, preset_mode=preset_mode
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of circulation fan."""
        if percentage <= 0:
            await self.async_turn_off()
            return

        await self.async_execute_circulation_fan_command(
            ERROR_SET_SPEED_FAILED, percentage=percentage
        )

    async def async_execute_circulation_fan_command(
        self,
        error_translation_key: str,
        percentage: int | None = None,
        preset_mode: str | None = None,
    ) -> None:
        """Execute circulation fan command with parameter handling."""
        command_params: dict[str, Any] = {}

        if not self.is_on:
            command_params["power_switch"] = True

        if percentage is not None and percentage > 0 and self._low_high_range:
            speed = math.ceil(
                percentage_to_ranged_value(self._low_high_range, percentage)
            )
            if speed is not None and speed > 0:
                command_params["speed"] = speed

        if preset_mode is not None:
            command_params["mode"] = preset_mode

        await self.async_send_command_and_update(
            error_translation_key, **command_params
        )
