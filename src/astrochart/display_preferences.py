"""Validated local display preferences; no network, telemetry or birth data."""
from dataclasses import dataclass
from PySide6.QtCore import QSettings

FONT_PERCENTS = (90, 100, 110, 120)
ROW_HEIGHTS = (21, 26, 30)
SYMBOL_SIZES = (14, 16, 18)


@dataclass(frozen=True)
class DisplayPreferences:
    font_percent: int = 100
    row_height: int = 21
    symbol_size: int = 16


def _saved_choice(settings, key, choices, fallback):
    try:
        value = int(settings.value(key, fallback))
    except (TypeError, ValueError):
        return fallback
    return value if value in choices else fallback


def read_preferences(settings):
    return DisplayPreferences(
        font_percent=_saved_choice(settings, "display/font_percent", FONT_PERCENTS, 100),
        row_height=_saved_choice(settings, "display/table_row_height", ROW_HEIGHTS, 21),
        symbol_size=_saved_choice(settings, "display/wheel_symbol_size", SYMBOL_SIZES, 16),
    )


def save_preferences(settings, prefs):
    if (not isinstance(prefs, DisplayPreferences)
            or prefs.font_percent not in FONT_PERCENTS
            or prefs.row_height not in ROW_HEIGHTS
            or prefs.symbol_size not in SYMBOL_SIZES):
        raise ValueError("הגדרות תצוגה לא נתמכות")
    settings.setValue("display/font_percent", prefs.font_percent)
    settings.setValue("display/table_row_height", prefs.row_height)
    settings.setValue("display/wheel_symbol_size", prefs.symbol_size)
    settings.sync()
    if settings.status() != QSettings.Status.NoError:
        raise OSError("לא ניתן לשמור הגדרות תצוגה מקומיות")
