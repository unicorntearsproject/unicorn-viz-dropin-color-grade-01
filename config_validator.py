"""Optional config validation for the color-grade-01 drop-in."""
from __future__ import annotations

from typing import Any


def validate_config(config_data: dict[str, Any]) -> list[str]:
    """Validate the ``[color_grade]`` section, returning any error strings."""
    errors: list[str] = []
    section = config_data.get('color_grade')
    if section is None:
        return errors
    if not isinstance(section, dict):
        return ['[color_grade] must be a table']

    if 'enabled' in section and not isinstance(section['enabled'], bool):
        errors.append('[color_grade] enabled must be a boolean')

    intensity = section.get('intensity')
    if intensity is not None:
        if not isinstance(intensity, (int, float)):
            errors.append('[color_grade] intensity must be a number')
        elif not (0.0 <= float(intensity) <= 1.0):
            errors.append('[color_grade] intensity must be in [0.0, 1.0]')

    for key in ('lut_dir', 'default_grade'):
        if key in section and not isinstance(section[key], str):
            errors.append(f'[color_grade] {key} must be a string')

    return errors
