"""Unit tests for color-grade-01 pure data + .cube LUT parsing."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

_GRADES_PATH = Path(__file__).resolve().parents[1] / 'grades.py'
_spec = importlib.util.spec_from_file_location('color_grade_grades_test', _GRADES_PATH)
grades = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = grades  # needed for Py3.14 dataclass annotation resolution
_spec.loader.exec_module(grades)


def _identity_cube(size: int = 2) -> str:
    lines = [f'TITLE "ident"', f'LUT_3D_SIZE {size}']
    for b in range(size):
        for g in range(size):
            for r in range(size):
                lines.append(
                    f'{r/(size-1):.6f} {g/(size-1):.6f} {b/(size-1):.6f}'
                )
    return '\n'.join(lines)


def test_builtin_grades_present_and_named() -> None:
    names = [g.name for g in grades.BUILTIN_GRADES]
    assert 'Neutral' in names
    assert len(names) == len(set(names))  # unique
    assert len(names) >= 5


def test_parse_cube_identity() -> None:
    lut = grades.parse_cube_lut(_identity_cube(2))
    assert lut.size == 2
    assert lut.data.shape == (8, 3)
    assert lut.data.dtype == np.float32
    # First entry is black, last is white.
    assert np.allclose(lut.data[0], [0, 0, 0])
    assert np.allclose(lut.data[-1], [1, 1, 1])


def test_parse_cube_red_varies_fastest() -> None:
    lut = grades.parse_cube_lut(_identity_cube(3))
    assert lut.size == 3
    # Index 1 should advance red only.
    assert lut.data[1][0] > 0.0
    assert np.allclose(lut.data[1][1:], 0.0)


def test_parse_cube_rejects_bad_count() -> None:
    bad = 'LUT_3D_SIZE 2\n0 0 0\n1 1 1\n'
    with pytest.raises(ValueError):
        grades.parse_cube_lut(bad)


def test_parse_cube_rejects_missing_size() -> None:
    with pytest.raises(ValueError):
        grades.parse_cube_lut('0 0 0\n1 1 1\n')


def test_parse_cube_rejects_1d() -> None:
    with pytest.raises(ValueError):
        grades.parse_cube_lut('LUT_1D_SIZE 2\n0 0 0\n1 1 1\n')


def test_parse_cube_ignores_comments_and_domain() -> None:
    text = '# comment\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n' + _identity_cube(2)
    lut = grades.parse_cube_lut(text)
    assert lut.data.shape == (8, 3)
