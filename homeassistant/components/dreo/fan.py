"""Support for Dreo fans."""

from __future__ import annotations

import logging
import math
from typing import Any

from hscloud.const import FAN_DEVICE
import voluptuous as vol

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.util.percentage import percentage_to_ranged_value

from . import DreoConfigEntry
from .const import (
    CIRCULATION_FAN_DEVICE_TYPE,
    CIRCULATION_FAN_MODES,
    ERROR_SET_OSCILLATE_FAILED,
    ERROR_SET_OSCILLATION_MODE_FAILED,
    ERROR_SET_PRESET_MODE_FAILED,
    ERROR_SET_SPEED_FAILED,
    ERROR_TURN_OFF_FAILED,
    ERROR_TURN_ON_FAILED,
    FAN_DEVICE_TYPE,
    OSCILLATION_MODE_TO_INT,
    OSCILLATION_MODES,
    SERVICE_SET_OSCILLATION_MODE,
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
        new_fans = []

        for device in config_entry.runtime_data.devices:
            device_type = device.get("deviceType")
            if device_type is None:
                continue

            device_id = str(device.get("deviceSn", ""))
            if not device_id:
                continue

            coordinator = config_entry.runtime_data.coordinators.get(device_id)
            if not coordinator:
                _LOGGER.error("Coordinator not found for device %s", device_id)
                continue

            # Create appropriate fan entity based on device type
            if device_type == FAN_DEVICE_TYPE:
                fan = DreoFan(device, coordinator)
                new_fans.append(fan)
            elif device_type == CIRCULATION_FAN_DEVICE_TYPE:
                fan = DreoCirculationFan(device, coordinator)
                new_fans.append(fan)

        if new_fans:
            async_add_entities(new_fans)

    # Register custom services for circulation fans
    platform = async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_OSCILLATION_MODE,
        {
            vol.Required("oscillation_mode"): vol.In(list(OSCILLATION_MODES.values()))
        },
        "async_set_oscillation_mode",
    )

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

    def __init__(
        self,
        device: dict[str, Any],
        coordinator: DreoDataUpdateCoordinator,
    ) -> None:
        """Initialize the Dreo fan."""
        super().__init__(device, coordinator, FAN_DEVICE_TYPE, None)

        model_config = FAN_DEVICE.get("config", {}).get(self._model, {})
        speed_range = model_config.get("speed_range")

        self._attr_preset_modes = model_config.get("preset_modes")
        self._low_high_range = speed_range

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
        if fan_state_data.available is None:
            self._attr_available = False
            return

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
        | FanEntityFeature.OSCILLATE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_is_on = False
    _attr_percentage = 0
    _attr_preset_mode = None
    _attr_oscillating = None
    _attr_oscillation_mode: str | None = None

    def __init__(
        self,
        device: dict[str, Any],
        coordinator: DreoDataUpdateCoordinator,
    ) -> None:
        """Initialize the Dreo circulation fan."""
        super().__init__(device, coordinator, CIRCULATION_FAN_DEVICE_TYPE, None)

        self._attr_preset_modes = list(CIRCULATION_FAN_MODES.keys())
        self._speed_levels = 9
        self._oscillation_modes = list(OSCILLATION_MODES.values())

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
        if fan_state_data.available is None:
            self._attr_available = False
            return

        self._attr_available = fan_state_data.available

        if not fan_state_data.is_on:
            self._attr_percentage = 0
            self._attr_preset_mode = None
            self._attr_oscillating = None
            self._attr_oscillation_mode = None
        else:
            self._attr_preset_mode = fan_state_data.mode
            self._attr_percentage = fan_state_data.speed_percentage
            # Store the specific oscillation mode
            if hasattr(fan_state_data, "oscillation_mode"):
                self._attr_oscillation_mode = fan_state_data.oscillation_mode
                # For Home Assistant compatibility, oscillating is true if not in fixed mode
                self._attr_oscillating = fan_state_data.oscillation_mode != "fixed"
            else:
                self._attr_oscillation_mode = None
                self._attr_oscillating = None

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

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set the oscillation of circulation fan."""
        osc_mode = 1 if oscillating else 0
        await self.async_execute_circulation_fan_command(
            ERROR_SET_OSCILLATE_FAILED, oscmode=osc_mode
        )

    async def async_set_oscillation_mode(self, oscillation_mode: str) -> None:
        """Set the specific oscillation mode of circulation fan."""
        if oscillation_mode not in OSCILLATION_MODE_TO_INT:
            _LOGGER.error("Invalid oscillation mode: %s", oscillation_mode)
            return
        
        osc_mode = OSCILLATION_MODE_TO_INT[oscillation_mode]
        await self.async_execute_circulation_fan_command(
            ERROR_SET_OSCILLATION_MODE_FAILED, oscmode=osc_mode
        )

    @property
    def oscillation_mode(self) -> str | None:
        """Return the current oscillation mode."""
        return self._attr_oscillation_mode

    @property
    def oscillation_modes(self) -> list[str]:
        """Return a list of available oscillation modes."""
        return self._oscillation_modes

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attrs = super().extra_state_attributes or {}
        attrs["oscillation_mode"] = self.oscillation_mode
        attrs["oscillation_modes"] = self.oscillation_modes
        return attrs

    async def async_execute_circulation_fan_command(
        self,
        error_translation_key: str,
        percentage: int | None = None,
        preset_mode: str | None = None,
        oscmode: int | None = None,
    ) -> None:
        """Execute circulation fan command with parameter handling."""
        command_params: dict[str, Any] = {}

        if not self.is_on:
            command_params["power_switch"] = True

        if percentage is not None and percentage > 0:
            # Convert percentage to speed level (1-9)
            speed_level = max(1, min(9, math.ceil((percentage / 100) * 9)))
            command_params["speed"] = speed_level

        if preset_mode is not None and preset_mode in CIRCULATION_FAN_MODES:
            command_params["mode"] = CIRCULATION_FAN_MODES[preset_mode]

        if oscmode is not None:
            command_params["oscmode"] = oscmode

        await self.async_send_command_and_update(
            error_translation_key, **command_params
        )
