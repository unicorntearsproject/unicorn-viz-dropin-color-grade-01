"""Pure (GL-free) colour-grade data: built-in looks + Adobe ``.cube`` LUT parsing.

Kept free of ``moderngl`` so it can be unit-tested in isolation and imported at
drop-in discovery time without a GL context.  The controller turns these data
structures into GPU programs / 3D textures.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(slots=True)
class ProceduralGrade:
    """A lift/gamma/gain + temperature/saturation/contrast colour look.

    All vectors are RGB triples.  Values are chosen to read as distinct,
    recognisable "looks" rather than physically-calibrated transforms.
    """

    name: str
    temp: float = 0.0          # warm (+) / cool (-) shift, ~[-1, 1]
    tint: float = 0.0          # magenta (+) / green (-) shift, ~[-1, 1]
    lift: tuple[float, float, float] = (0.0, 0.0, 0.0)
    gamma: tuple[float, float, float] = (1.0, 1.0, 1.0)
    gain: tuple[float, float, float] = (1.0, 1.0, 1.0)
    saturation: float = 1.0
    contrast: float = 1.0


@dataclass(slots=True)
class LutGrade:
    """A 3D LUT look loaded from an Adobe ``.cube`` file."""

    name: str
    size: int
    data: np.ndarray = field(repr=False)  # shape (size**3, 3), float32, RGB fastest=R


# Built-in procedural looks — always available, no asset files required.
BUILTIN_GRADES: tuple[ProceduralGrade, ...] = (
    ProceduralGrade('Neutral'),
    ProceduralGrade(
        'Teal & Orange', temp=0.18, tint=-0.04,
        lift=(0.0, 0.0, 0.02), gain=(1.06, 1.0, 0.95),
        saturation=1.15, contrast=1.12,
    ),
    ProceduralGrade(
        'Warm Sunset', temp=0.35, tint=0.05,
        gain=(1.1, 1.0, 0.88), saturation=1.1, contrast=1.05,
    ),
    ProceduralGrade(
        'Cool Night', temp=-0.32, tint=-0.02,
        lift=(0.0, 0.0, 0.03), gain=(0.9, 0.98, 1.12),
        saturation=0.95, contrast=1.1,
    ),
    ProceduralGrade(
        'Noir', temp=-0.05, saturation=0.15, contrast=1.3,
        gamma=(0.95, 0.95, 0.95),
    ),
    ProceduralGrade(
        'Vibrant Pop', saturation=1.45, contrast=1.18,
        gain=(1.04, 1.02, 1.04),
    ),
    ProceduralGrade(
        'Faded Film', temp=0.08, lift=(0.05, 0.04, 0.04),
        gamma=(1.08, 1.06, 1.04), saturation=0.85, contrast=0.92,
    ),
    ProceduralGrade(
        'Cyberpunk', temp=-0.12, tint=0.22,
        gain=(1.08, 0.94, 1.15), saturation=1.3, contrast=1.15,
    ),
)


def parse_cube_lut(text: str) -> LutGrade:
    """Parse an Adobe ``.cube`` 3D LUT into a :class:`LutGrade`.

    Supports ``LUT_3D_SIZE`` cubes with red varying fastest (Adobe order).
    Ignores comments, ``TITLE``, and ``DOMAIN_MIN/MAX`` lines.  Raises
    ``ValueError`` on malformed input or unsupported 1D LUTs.
    """
    size = 0
    title = ''
    rows: list[tuple[float, float, float]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        upper = line.upper()
        if upper.startswith('LUT_3D_SIZE'):
            size = int(line.split()[-1])
            continue
        if upper.startswith('LUT_1D_SIZE'):
            raise ValueError('1D .cube LUTs are not supported')
        if upper.startswith('TITLE'):
            title = line.split('"')[1] if '"' in line else line.split(maxsplit=1)[-1]
            continue
        if upper.startswith(('DOMAIN_MIN', 'DOMAIN_MAX', 'LUT_3D_INPUT_RANGE')):
            continue
        parts = line.split()
        if len(parts) == 3:
            try:
                rows.append((float(parts[0]), float(parts[1]), float(parts[2])))
            except ValueError:
                continue
    if size <= 0:
        raise ValueError('missing LUT_3D_SIZE')
    if len(rows) != size ** 3:
        raise ValueError(f'expected {size ** 3} entries, got {len(rows)}')
    data = np.asarray(rows, dtype=np.float32)
    return LutGrade(name=title or 'LUT', size=size, data=data)
