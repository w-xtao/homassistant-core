"""Constants for the Dreo integration."""

DOMAIN = "dreo"
FAN_DEVICE_TYPE = "fan"
CIRCULATION_FAN_DEVICE_TYPE = "circulation_fan"

# Services
SERVICE_SET_OSCILLATION_MODE = "set_oscillation_mode"

# Circulation fan modes
CIRCULATION_FAN_MODES = {
    "Normal": 1,
    "Auto": 2,
    "Sleep": 3,
    "Smart": 4,
    "Turbo": 5,
    "Custom": 6,
}

# Oscillation modes for circulation fan
OSCILLATION_MODES = {
    0: "fixed",  # 定点出风模式(不摇头或巡航)
    1: "horizontal",  # 左右摇头模式
    2: "vertical",  # 上下摇头模式
    3: "both",  # 上下左右摇头模式
}

# Reverse mapping for API calls
OSCILLATION_MODE_TO_INT = {v: k for k, v in OSCILLATION_MODES.items()}

# Error messages
ERROR_TURN_ON_FAILED = "turn_on_failed"
ERROR_TURN_OFF_FAILED = "turn_off_failed"
ERROR_SET_PRESET_MODE_FAILED = "set_preset_mode_failed"
ERROR_SET_SPEED_FAILED = "set_speed_failed"
ERROR_SET_OSCILLATE_FAILED = "set_oscillate_failed"
ERROR_SET_OSCILLATION_MODE_FAILED = "set_oscillation_mode_failed"
