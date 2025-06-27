"""Support for Dreo device RGB lights."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DreoConfigEntry
from .const import (
    CIR_FAN_DEVICE_TYPE,
    ERROR_SET_BRIGHTNESS_FAILED,
    ERROR_TURN_OFF_FAILED,
    ERROR_TURN_ON_FAILED,
)
from .coordinator import DreoDataUpdateCoordinator
from .entity import DreoEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DreoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Light from a config entry."""

    @callback
    def async_add_light_devices() -> None:
        """Add light devices."""
        new_lights = []

        for device in config_entry.runtime_data.devices:
            device_type = device.get("deviceType")
            if device_type != CIR_FAN_DEVICE_TYPE:
                continue

            device_id = str(device.get("deviceSn", ""))
            if not device_id:
                continue

            coordinator = config_entry.runtime_data.coordinators.get(device_id)
            if not coordinator:
                _LOGGER.error("Coordinator not found for light device %s", device_id)
                continue

            light = DreoCirculationFanLight(device, coordinator)
            new_lights.append(light)

        if new_lights:
            async_add_entities(new_lights)

    async_add_light_devices()


class DreoCirculationFanLight(DreoEntity, LightEntity):
    """Dreo Circulation Fan RGB Light."""

    _attr_supported_features = LightEntityFeature.TRANSITION
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_is_on = False
    _attr_brightness = 0

    def __init__(
        self,
        device: dict[str, Any],
        coordinator: DreoDataUpdateCoordinator,
    ) -> None:
        """Initialize the Dreo circulation fan RGB light."""
        super().__init__(device, coordinator, "light", "RGB Light")

        device_id = device.get("deviceSn")
        self._attr_unique_id = f"{device_id}_rgb_light"

    @callback
    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        self._update_attributes()
        super()._handle_coordinator_update()

    def _update_attributes(self):
        """Update attributes from coordinator data."""
        if not self.coordinator.data:
            return

        fan_data = self.coordinator.data
        if fan_data.available is None:
            self._attr_available = False
            return

        self._attr_available = fan_data.available

        if fan_data.rgb_state is not None:
            self._attr_is_on = fan_data.rgb_state

        if fan_data.rgb_brightness is not None:
            # Convert percentage (0-100) to HA brightness (0-255)
            self._attr_brightness = int((fan_data.rgb_brightness / 100) * 255)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the RGB light."""
        command_params: dict[str, Any] = {"rgb_switch": True}

        if ATTR_BRIGHTNESS in kwargs:
            brightness_percent = int((kwargs[ATTR_BRIGHTNESS] / 255) * 100)
            command_params["rgb_brightness"] = max(1, brightness_percent)

        await self.async_send_command_and_update(
            ERROR_SET_BRIGHTNESS_FAILED
            if ATTR_BRIGHTNESS in kwargs
            else ERROR_TURN_ON_FAILED,
            **command_params,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the RGB light."""
        await self.async_send_command_and_update(
            ERROR_TURN_OFF_FAILED, rgb_switch=False
        )
