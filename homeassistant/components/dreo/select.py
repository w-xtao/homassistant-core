"""Support for Dreo select entities."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DreoConfigEntry
from .const import (
    AIR_FAN_OSCILLATE_ENTITY,
    CIR_FAN_DEVICE_TYPE,
    CIR_FAN_OSCILLATE_ENTITY,
    CIRCULATION_FAN_DEVICE_TYPE,
    ERROR_SET_OSCILLATE_FAILED,
)
from .coordinator import DreoDataUpdateCoordinator
from .entity import DreoEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DreoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Dreo select entities from a config entry."""

    @callback
    def async_add_select_entities() -> None:
        """Add select entities."""
        new_selects = []

        for device in config_entry.runtime_data.devices:
            device_type = device.get("deviceType")
            if device_type != CIRCULATION_FAN_DEVICE_TYPE:
                continue

            device_id = device.get("deviceSn")
            if not device_id:
                continue

            coordinator = config_entry.runtime_data.coordinators.get(device_id)
            if not coordinator:
                _LOGGER.error("Coordinator not found for device %s", device_id)
                continue

            config = coordinator.model_config
            select_options = config.get("selectOptions", [])
            if len(select_options) > 1:
                select_entity = DreoOscillationSelect(device, coordinator)
                new_selects.append(select_entity)

        if new_selects:
            async_add_entities(new_selects)

    async_add_select_entities()


class DreoOscillationSelect(DreoEntity, SelectEntity):
    """Dreo circulation fan oscillation direction select."""

    def __init__(
        self,
        device: dict[str, Any],
        coordinator: DreoDataUpdateCoordinator,
    ) -> None:
        """Initialize the oscillation select."""
        super().__init__(
            device, coordinator, CIR_FAN_DEVICE_TYPE, CIR_FAN_OSCILLATE_ENTITY
        )

        select_options = coordinator.model_config.get("selectOptions", [])

        self._select_options = select_options
        self._attr_options = []

        direction_labels = {
            "fixed": "Fixed",
            "horizontal": "Horizontal",
            "vertical": "Vertical",
            "both": "Both",
        }

        for direction in select_options:
            label = direction_labels.get(direction, direction)
            self._attr_options.append(label)

        self._attr_name = AIR_FAN_OSCILLATE_ENTITY
        self._attr_icon = "mdi:fan-chevron-up"

        self._attr_current_option = (
            self._attr_options[0] if self._attr_options else None
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.data:
            return

        fan_data = self.coordinator.data
        if (
            hasattr(fan_data, "oscillation_mode")
            and fan_data.oscillation_mode is not None
        ):
            current_mode = fan_data.oscillation_mode
            if current_mode in self._select_options:
                index = self._select_options.index(current_mode)
                self._attr_current_option = self._attr_options[index]
        else:
            self._attr_current_option = (
                self._attr_options[0] if self._attr_options else None
            )

        super()._handle_coordinator_update()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if option not in self._attr_options:
            _LOGGER.error("Invalid oscillation option: %s", option)
            return

        option_index = self._attr_options.index(option)
        select_option = self._select_options[option_index]

        direction_modes = self.coordinator.model_config.get("selectOptions", [])
        if select_option in direction_modes:
            await self.async_send_command_and_update(
                ERROR_SET_OSCILLATE_FAILED, oscmode=select_option
            )
        else:
            _LOGGER.error(
                "Oscillation mode %s not found in device config", select_option
            )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self.coordinator.data.available
        )
