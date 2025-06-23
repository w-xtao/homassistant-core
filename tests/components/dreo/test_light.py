"""Test dreo light platform."""

from unittest.mock import MagicMock, patch

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from . import init_integration


async def test_circulation_fan_rgb_light_setup(hass: HomeAssistant) -> None:
    """Test circulation fan RGB light setup."""
    with patch("homeassistant.components.dreo.HsCloud") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = [
            {
                "deviceSn": "test-circulation-fan-123",
                "model": "DR-HTF001S",
                "deviceName": "Living Room Circulation Fan",
                "deviceType": "circulation_fan",
                "config": {
                    "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
                    "speed_range": [1, 9],
                },
            }
        ]
        mock_client.get_status.return_value = {
            "power_switch": True,
            "connected": True,
            "mode": 1,
            "speed": 5,
            "rgb_switch": True,
            "rgb_brightness": 50,
        }

        config_entry = await init_integration(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Check if RGB light entity exists
    light_entity = "light.living_room_circulation_fan_rgb_light"
    state = hass.states.get(light_entity)
    assert state is not None
    assert state.state == STATE_ON
    # Brightness should be converted from 50% to 127 (50% of 255)
    assert state.attributes[ATTR_BRIGHTNESS] == 127


async def test_rgb_light_turn_off(hass: HomeAssistant) -> None:
    """Test RGB light turn off service."""
    with patch("homeassistant.components.dreo.HsCloud") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = [
            {
                "deviceSn": "test-circulation-fan-456",
                "model": "DR-HTF001S",
                "deviceName": "Bedroom Circulation Fan",
                "deviceType": "circulation_fan",
                "config": {
                    "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
                    "speed_range": [1, 9],
                },
            }
        ]
        mock_client.get_status.return_value = {
            "power_switch": True,
            "connected": True,
            "rgb_switch": True,
            "rgb_brightness": 80,
        }
        mock_client.update_status = MagicMock()

        config_entry = await init_integration(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    light_entity = "light.bedroom_circulation_fan_rgb_light"
    
    # Turn off RGB light
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: light_entity},
        blocking=True,
    )

    # Should call update_status with rgb_switch=False
    mock_client.update_status.assert_called_with("test-circulation-fan-456", rgb_switch=False)


async def test_rgb_light_turn_on_with_brightness(hass: HomeAssistant) -> None:
    """Test RGB light turn on with brightness service."""
    with patch("homeassistant.components.dreo.HsCloud") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = [
            {
                "deviceSn": "test-circulation-fan-789",
                "model": "DR-HTF001S",
                "deviceName": "Office Circulation Fan",
                "deviceType": "circulation_fan",
                "config": {
                    "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
                    "speed_range": [1, 9],
                },
            }
        ]
        mock_client.get_status.return_value = {
            "power_switch": True,
            "connected": True,
            "rgb_switch": False,
            "rgb_brightness": 0,
        }
        mock_client.update_status = MagicMock()

        config_entry = await init_integration(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    light_entity = "light.office_circulation_fan_rgb_light"
    
    # Turn on RGB light with 75% brightness (191 in HA scale)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: light_entity, ATTR_BRIGHTNESS: 191},
        blocking=True,
    )

    # Should call update_status with rgb_switch=True and rgb_brightness=75
    mock_client.update_status.assert_called_with(
        "test-circulation-fan-789", 
        rgb_switch=True, 
        rgb_brightness=75
    ) 