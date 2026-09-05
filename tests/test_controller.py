"""Controller tests for color-grade-01.

GL-dependent assertions run only when a headless GL context is available;
otherwise they are skipped (e.g. CI without a GPU/EGL).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

_MOD = Path(__file__).resolve().parents[1] / 'color_grade_controller.py'
_spec = importlib.util.spec_from_file_location('color_grade_controller_test', _MOD)
ctrl_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = ctrl_mod
_spec.loader.exec_module(ctrl_mod)
ColorGradeController = ctrl_mod.ColorGradeController


@pytest.fixture
def ctx():
    moderngl = pytest.importorskip('moderngl')
    try:
        c = moderngl.create_standalone_context()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f'no headless GL context: {exc}')
    yield c
    c.release()


def _grade(ctx, **cfg):
    return ColorGradeController(ctx, 16, 16, cfg)


def test_starts_on_random_non_neutral_when_enabled(ctx) -> None:
    c = _grade(ctx, start_enabled=True)
    assert c.active_name != 'Neutral'
    c.destroy()


def test_default_grade_selection(ctx) -> None:
    c = _grade(ctx, start_enabled=True, default_grade='Noir')
    assert c.active_name == 'Noir'
    c.destroy()


def test_is_active_respects_enable_and_neutral(ctx) -> None:
    c = _grade(ctx, start_enabled=False, default_grade='Noir')
    assert c.is_active() is False
    c.toggle()
    assert c.is_active() is True
    c.select_grade('Neutral')
    assert c.is_active() is False
    c.destroy()


def test_intensity_clamps(ctx) -> None:
    c = _grade(ctx, start_enabled=True)
    assert c.set_intensity(5.0) == 1.0
    assert c.set_intensity(-1.0) == 0.0
    assert c.is_active() is False  # intensity 0 disables the pass
    c.destroy()


def test_cycle_wraps(ctx) -> None:
    c = _grade(ctx, start_enabled=True, default_grade='Neutral')
    first = c.active_name
    names = [first]
    for _ in range(len(c._grades) - 1):
        names.append(c.next_grade())
    assert c.next_grade() == first  # wrapped back round
    assert len(set(names)) == len(names)
    c.destroy()


def test_procedural_grade_changes_pixels(ctx) -> None:
    import moderngl
    src = ctx.texture((8, 8), 4)
    src.filter = (moderngl.NEAREST, moderngl.NEAREST)
    sf = ctx.framebuffer(color_attachments=[src])
    sf.use()
    ctx.clear(0.5, 0.25, 0.75, 1.0)
    dst = ctx.texture((8, 8), 4)
    df = ctx.framebuffer(color_attachments=[dst])

    c = _grade(ctx, start_enabled=True, default_grade='Vibrant Pop', intensity=1.0)
    assert c.apply(src, df, 0.016, 0.0, 0.0, 0.0, 0.0) is True
    px = np.frombuffer(df.read(components=4), dtype=np.uint8).reshape(8, 8, 4)[0, 0]
    # Vibrant Pop boosts saturation/contrast: result differs from the source
    # and is not black (the sampler-completeness regression).
    assert tuple(int(v) for v in px[:3]) != (128, 64, 191)
    assert int(px[0]) + int(px[1]) + int(px[2]) > 0
    c.destroy()


# ------------------------------------------------------------ control room

class _FakeVJApi:
    def __init__(self) -> None:
        self.panels: dict[str, object] = {}

    def register_midi_actions(self, section, actions) -> None:
        pass

    def register_midi_action_handler(self, action, fn) -> None:
        pass

    def register_operator_panel(self, panel) -> None:
        self.panels[panel.name] = panel

    def unregister_operator_panel(self, name: str) -> bool:
        return self.panels.pop(name, None) is not None


def test_set_vj_api_registers_the_panel_on_the_fx_page(ctx) -> None:
    c = _grade(ctx)
    api = _FakeVJApi()
    c.set_vj_api(api)
    panel = api.panels['color_grade']
    assert panel.title == 'Color Grade' and panel.page == 'fx' and panel.size == 'small'
    assert panel.content == c._operator_panel_content
    assert panel.on_action == c._operator_panel_action
    assert set(panel.tooltips) == {'toggle', 'prev', 'next', 'int_down', 'int_up'}
    c.destroy()


def test_panel_content_mirrors_state(ctx) -> None:
    c = _grade(ctx, start_enabled=True, default_grade='Noir')
    c.set_intensity(0.6)
    content = c._operator_panel_content()
    assert content.status == 'ON'
    assert content.rows[0].label == 'Look' and content.rows[0].value == 'Noir'
    assert content.meters[0].value == pytest.approx(0.6)
    assert content.buttons[0].active is True
    c.destroy()


def test_panel_actions_match_the_hotkeys(ctx) -> None:
    c = _grade(ctx, start_enabled=False)
    before = c.enabled
    msg = c._operator_panel_action('toggle', None)
    assert c.enabled != before
    assert msg == f'Color grade {"on" if c.enabled else "off"} ({c.active_name})'
    assert c._operator_panel_action('next', None) == f'Grade: {c.active_name}'
    assert c._operator_panel_action('prev', None) == f'Grade: {c.active_name}'
    up = c._operator_panel_action('int_up', None)
    assert up == f'Grade intensity {c.intensity:.2f}'
    assert c._operator_panel_action('nope', None) is None
    c.destroy()


def test_destroy_unregisters_the_panel(ctx) -> None:
    c = _grade(ctx)
    api = _FakeVJApi()
    c.set_vj_api(api)
    c.destroy()
    assert 'color_grade' not in api.panels
