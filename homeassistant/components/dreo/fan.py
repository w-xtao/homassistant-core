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
    CIRCULATION_FAN_DEVICE_TYPE,
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

            if device_type == FAN_DEVICE_TYPE:
                fan = DreoFan(device, coordinator)
                new_fans.append(fan)
            elif device_type == CIRCULATION_FAN_DEVICE_TYPE:
                fan = DreoCirculationFan(device, coordinator)
                new_fans.append(fan)

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

    def __init__(
        self,
        device: dict[str, Any],
        coordinator: DreoDataUpdateCoordinator,
    ) -> None:
        """Initialize the Dreo fan."""
        super().__init__(device, coordinator, FAN_DEVICE_TYPE, None)

        model_config = coordinator.model_config
        speed_range = model_config.get("speed_range")

        self._low_high_range = tuple(speed_range)
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
        | FanEntityFeature.DIRECTION
        | FanEntityFeature.OSCILLATE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_is_on = False
    _attr_percentage = 0
    _attr_preset_mode = None
    _attr_swing_mode = SWING_OFF
    _attr_swing_modes = [SWING_OFF, SWING_HORIZONTAL, SWING_VERTICAL, SWING_BOTH]
    _oscillation_directions: list[str] = []

    def __init__(
        self,
        device: dict[str, Any],
        coordinator: DreoDataUpdateCoordinator,
    ) -> None:
        """Initialize the Dreo circulation fan."""
        super().__init__(device, coordinator, CIRCULATION_FAN_DEVICE_TYPE, None)

        config = coordinator.model_config
        self._attr_preset_modes = config.get("preset_modes")
        self._speed_levels = config.get("speed_range")
        
        # Set up oscillation directions - support both legacy and new format
        legacy_directions = config.get("directions", [])  # 保持向后兼容
        shaking_directions = config.get("shakingDirections", [])
        
        # Use standard oscillation modes if available, otherwise fall back to legacy
        if shaking_directions:
            self._oscillation_directions = [
                LEGACY_OSCILLATION_MAPPING.get(mode, mode) 
                for mode in shaking_directions
            ]
        elif legacy_directions:
            self._oscillation_directions = legacy_directions
        else:
            # Default oscillation modes
            self._oscillation_directions = [OSCILLATION_FIXED, OSCILLATION_HORIZONTAL]

        speed_range = config.get("speed_range")
        if speed_range and len(speed_range) >= 2:
            self._low_high_range = tuple(speed_range)
        else:
            self._low_high_range = None

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
        else:
            self._attr_preset_mode = fan_state_data.mode
            self._attr_percentage = fan_state_data.speed_percentage
            if hasattr(fan_state_data, "oscillation_mode") and fan_state_data.oscillation_mode:
                # Normalize oscillation mode to standard format
                normalized_mode = LEGACY_OSCILLATION_MAPPING.get(
                    fan_state_data.oscillation_mode, fan_state_data.oscillation_mode
                )
                self._attr_current_direction = normalized_mode
                self._attr_oscillating = normalized_mode != OSCILLATION_FIXED
                
                # Set swing mode based on oscillation type
                if normalized_mode == OSCILLATION_HORIZONTAL:
                    self._attr_swing_mode = SWING_HORIZONTAL
                elif normalized_mode == OSCILLATION_VERTICAL:
                    self._attr_swing_mode = SWING_VERTICAL
                elif normalized_mode == OSCILLATION_BOTH:
                    self._attr_swing_mode = SWING_BOTH
                else:
                    self._attr_swing_mode = SWING_OFF

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

    async def async_set_oscillation_mode(self, oscillation_mode: str) -> None:
        """Set the specific oscillation mode of circulation fan."""
        # Support both legacy and new oscillation mode formats
        direction_modes = self.coordinator.model_config.get("shakingDirections", [])
        
        # Normalize the input oscillation mode
        normalized_mode = oscillation_mode
        if oscillation_mode in LEGACY_OSCILLATION_MAPPING.values():
            # Find the original key for the normalized mode
            for key, value in LEGACY_OSCILLATION_MAPPING.items():
                if value == oscillation_mode and key in direction_modes:
                    normalized_mode = key
                    break

        if normalized_mode not in direction_modes:
            _LOGGER.error(
                "Invalid oscillation mode: %s. Available modes: %s", 
                oscillation_mode, direction_modes
            )
            return

        osc_mode = direction_modes.index(normalized_mode)
        await self.async_execute_circulation_fan_command(
            ERROR_SET_OSCILLATE_FAILED, oscmode=osc_mode
        )

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set swing mode (horizontal, vertical, both, off)."""
        # Map swing modes to oscillation modes
        swing_to_oscillation = {
            SWING_HORIZONTAL: OSCILLATION_HORIZONTAL,
            SWING_VERTICAL: OSCILLATION_VERTICAL, 
            SWING_BOTH: OSCILLATION_BOTH,
            SWING_OFF: OSCILLATION_FIXED,
        }
        
        if swing_mode not in swing_to_oscillation:
            _LOGGER.error("Invalid swing mode: %s", swing_mode)
            return
            
        oscillation_mode = swing_to_oscillation[swing_mode]
        await self.async_set_oscillation_mode(oscillation_mode)

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

        if percentage is not None and percentage > 0 and self._low_high_range:
            speed = math.ceil(
                percentage_to_ranged_value(self._low_high_range, percentage)
            )
            if speed is not None and speed > 0:
                command_params["speed"] = speed

        if preset_mode is not None:
            command_params["mode"] = preset_mode

        if oscmode is not None:
            command_params["oscmode"] = oscmode

        await self.async_send_command_and_update(
            error_translation_key, **command_params
        )
