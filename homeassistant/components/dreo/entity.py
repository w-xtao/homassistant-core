"""Dreo device base entity."""

from functools import partial
from typing import Any

from pydreo.exceptions import (
    DreoAccessDeniedException,
    DreoBusinessException,
    DreoException,
    DreoFlowControlException,
)

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DreoDataUpdateCoordinator


class DreoEntity(CoordinatorEntity[DreoDataUpdateCoordinator]):
    """Representation of a base Dreo Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device: dict[str, Any],
        coordinator: DreoDataUpdateCoordinator,
        unique_id_suffix: str | None = None,
        name: str | None = None,
    ) -> None:
        """Initialize the Dreo entity."""

        super().__init__(coordinator)
        self._device_id = device.get("deviceSn")
        self._model = device.get("model")
        self._attr_name = name

        if unique_id_suffix:
            self._attr_unique_id = f"{self._device_id}_{unique_id_suffix}"
        else:
            self._attr_unique_id = self._device_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self._device_id))},
            manufacturer="Dreo",
            model=self._model,
            name=device.get("deviceName"),
            sw_version=device.get("moduleFirmwareVersion"),
            hw_version=device.get("mcuFirmwareVersion"),
        )

    @property
    def available(self) -> bool:
        """Return if entity is available: coordinator success AND device online."""
        base_available = super().available
        data = getattr(self.coordinator, "data", None)
        return (
            base_available
            and data is not None
            and bool(getattr(self, "_attr_available", False))
        )

    async def async_send_command_and_update(
        self, error_translation_key: str, **kwargs: Any
    ) -> None:
        """Call a device command handling error messages and update entity state."""

        try:
            await self.coordinator.hass.async_add_executor_job(
                partial(
                    self.coordinator.client.update_status, self._device_id, **kwargs
                )
            )
            await self.coordinator.async_refresh()
        except (
            DreoException,
            DreoBusinessException,
            DreoAccessDeniedException,
            DreoFlowControlException,
        ) as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key=error_translation_key
            ) from ex

    def get_coordinator_field(self, field_name: str, default: Any = None) -> Any:
        """Get a field value from coordinator data if it exists and is not None."""
        if not self.coordinator.data:
            return default

        if hasattr(self.coordinator.data, field_name):
            value = getattr(self.coordinator.data, field_name)
            return value if value is not None else default

        return default
