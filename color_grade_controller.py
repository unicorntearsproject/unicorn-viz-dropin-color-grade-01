"""Global colour-grade / LUT post-process pass for unicorn-viz (color-grade-01).

A single persistent post-FX pass that sits in the global post chain (after
postfx-01). It applies either a built-in procedural "look" (lift/gamma/gain +
temperature/saturation/contrast) or a 3D LUT loaded from an Adobe ``.cube``
file, blended against the source by an ``intensity`` mix.

Contract matches :class:`PostFxController` so the app can drive it through the
shared post chain: ``apply(src_tex, dst_fbo, dt, bass, mid, treble, beat)``.
The pass renders directly into ``dst_fbo`` (reading its size for the viewport),
so it needs no internal render target and no resize wiring.

Pure data + ``.cube`` parsing lives in :mod:`grades` for unit-testing without
a GL context.
"""
from __future__ import annotations

__version__ = '0.10.0'

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any

import moderngl
import numpy as np

log = logging.getLogger(__name__)

_GRADES_PATH = Path(__file__).resolve().parent / 'grades.py'
_g_spec = importlib.util.spec_from_file_location('color_grade_grades', _GRADES_PATH)
if _g_spec is None or _g_spec.loader is None:  # pragma: no cover - import guard
    raise ImportError(f'color-grade-01: failed to load {_GRADES_PATH}')
_grades = importlib.util.module_from_spec(_g_spec)
# Register before exec so dataclass annotation resolution (Py3.14) can find the
# module globals via sys.modules[cls.__module__].
sys.modules[_g_spec.name] = _grades
_g_spec.loader.exec_module(_grades)
ProceduralGrade = _grades.ProceduralGrade
LutGrade = _grades.LutGrade
BUILTIN_GRADES = _grades.BUILTIN_GRADES
parse_cube_lut = _grades.parse_cube_lut


DROPIN_CAPABILITIES = {
    'name': 'color_grade',
    'class_symbol': 'ColorGradeController',
    'subsystem_name': 'color_grade',
    'key_handler_attr': 'handle_key',
}

HELP_ENTRIES = [
    ('Color Grade', 'Ctrl+Shift+Alt+L', 'Toggle global color grade on/off'),
    ('Color Grade', 'Ctrl+Shift+Alt+.', 'Next color-grade look / LUT'),
    ('Color Grade', 'Ctrl+Shift+Alt+,', 'Previous color-grade look / LUT'),
    ('Color Grade', 'Ctrl+Shift+Alt+;', 'Grade intensity up'),
    ('Color Grade', "Ctrl+Shift+Alt+'", 'Grade intensity down'),
]

_VERT = """
#version 330
in vec2 in_vert;
out vec2 v_uv;
void main() {
    v_uv = in_vert * 0.5 + 0.5;
    gl_Position = vec4(in_vert, 0.0, 1.0);
}
"""

_FRAG = """
#version 330
// Global colour-grade pass.
// Uniforms:
//   tex        — source frame (unit 0)
//   uLut       — 3D LUT (unit 1), used when uMode == 1
//   uMode      — 0 = procedural grade, 1 = 3D LUT
//   uIntensity — blend against source [0,1]
//   uLutSize   — LUT edge size (for texel-centre correction)
//   procedural params: uTemp, uTint, uLift, uGamma, uGain, uSat, uContrast
// Produces fragColor = mix(src, graded, uIntensity).

uniform sampler2D tex;
uniform sampler3D uLut;
uniform int   uMode;
uniform float uIntensity;
uniform float uLutSize;
uniform float uTemp;
uniform float uTint;
uniform vec3  uLift;
uniform vec3  uGamma;
uniform vec3  uGain;
uniform float uSat;
uniform float uContrast;

in vec2 v_uv;
out vec4 fragColor;

vec3 applyProcedural(vec3 c) {
    // Temperature/tint as simple channel pushes (punchy — built for the floor).
    c.r += uTemp * 0.16;
    c.b -= uTemp * 0.16;
    c.g += uTint * 0.16;
    // Lift / gamma / gain (ASC-CDL-ish ordering).
    c = c * uGain + uLift;
    c = pow(max(c, 0.0), 1.0 / max(uGamma, vec3(1e-3)));
    // Contrast around 0.5 mid-grey.
    c = (c - 0.5) * uContrast + 0.5;
    // Saturation around luma.
    float luma = dot(c, vec3(0.2126, 0.7152, 0.0722));
    c = mix(vec3(luma), c, uSat);
    return clamp(c, 0.0, 1.0);
}

vec3 applyLut(vec3 c) {
    vec3 uvw = (clamp(c, 0.0, 1.0) * (uLutSize - 1.0) + 0.5) / uLutSize;
    return texture(uLut, uvw).rgb;
}

void main() {
    vec3 src = texture(tex, v_uv).rgb;
    vec3 graded = (uMode == 1) ? applyLut(src) : applyProcedural(src);
    fragColor = vec4(mix(src, graded, clamp(uIntensity, 0.0, 1.0)), 1.0);
}
"""


class ColorGradeController:
    """Runtime controller for the global colour-grade post pass."""

    NAME = 'Color Grade'

    def __init__(
        self,
        ctx: moderngl.Context,
        width: int,
        height: int,
        cfg: dict[str, Any] | None = None,
    ) -> None:
        self._ctx = ctx
        self._width = width
        self._height = height
        self._cfg = dict(cfg or {})
        self._vj_api: Any = None

        # ``enabled`` gates loading (host); ``start_enabled`` decides whether the
        # grade is applied at boot.  Defaults OFF (owner decision 2026-09-09: a
        # fresh install shows the effects ungraded; the look is opt-in).
        self.enabled = bool(self._cfg.get('start_enabled', False))
        self._intensity = float(np.clip(self._cfg.get('intensity', 0.85), 0.0, 1.0))
        self._rng = np.random.default_rng()

        # Grade list: built-in procedural looks + any .cube LUTs found on disk.
        self._grades: list[Any] = list(BUILTIN_GRADES)
        self._lut_textures: dict[int, moderngl.Texture] = {}
        self._load_luts()

        # GL program + fullscreen quad.
        self._prog = ctx.program(vertex_shader=_VERT, fragment_shader=_FRAG)
        verts = np.array([-1, -1, -1, 1, 1, -1, 1, 1], dtype=np.float32)
        self._vbo = ctx.buffer(verts)
        self._vao = ctx.vertex_array(self._prog, [(self._vbo, '2f', 'in_vert')])

        # A 1³ dummy 3D texture keeps the uLut sampler3D *complete* even in
        # procedural mode. Without it the sampler defaults to unit 0 (the 2D
        # source), which is an incomplete sampler3D and renders the frame black.
        self._dummy_lut = ctx.texture3d(
            (1, 1, 1), 3, np.zeros((1, 3), dtype=np.float32).tobytes(), dtype='f4'
        )
        self._dummy_lut.filter = (moderngl.LINEAR, moderngl.LINEAR)

        self._index = self._resolve_initial_index()

    # ----------------------------------------------------------------- loading
    def _load_luts(self) -> None:
        # Default to the repo-level assets/luts/ so dropping a .cube file in
        # "just works" with no config.  Any [color_grade] lut_dir overrides it.
        raw = self._cfg.get('lut_dir') or 'assets/luts'
        lut_dir = Path(raw).expanduser()
        if not lut_dir.is_absolute():
            lut_dir = Path(__file__).resolve().parents[2] / lut_dir
        if not lut_dir.is_dir():
            return
        for path in sorted(lut_dir.glob('*.cube')):
            try:
                lut = parse_cube_lut(path.read_text(encoding='utf-8', errors='ignore'))
                lut.name = path.stem
                idx = len(self._grades)
                self._grades.append(lut)
                tex = self._ctx.texture3d(
                    (lut.size, lut.size, lut.size), 3,
                    lut.data.tobytes(), dtype='f4',
                )
                tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
                tex.repeat_x = tex.repeat_y = tex.repeat_z = False
                self._lut_textures[idx] = tex
            except Exception as exc:
                log.warning('color-grade: failed to load LUT %s: %s', path.name, exc)

    def _resolve_initial_index(self) -> int:
        """Pick the starting grade — honouring config, else random (non-neutral)."""
        want = str(self._cfg.get('default_grade', 'random') or 'random').strip()
        if want.lower() not in ('', 'random'):
            for i, grade in enumerate(self._grades):
                if grade.name.lower() == want.lower():
                    return i
        # Random non-neutral look so two runs look distinct from frame 0.
        candidates = [i for i, g in enumerate(self._grades) if g.name != 'Neutral']
        return int(self._rng.choice(candidates)) if candidates else 0

    # ------------------------------------------------------------- public API
    def set_vj_api(self, api: Any) -> None:
        self._vj_api = api
        try:
            api.register_midi_actions('Color Grade', [
                ('color_grade_toggle', 'Toggle color grade'),
                ('color_grade_next',   'Next color grade'),
                ('color_grade_prev',   'Previous color grade'),
            ])
            api.register_midi_action_handler('color_grade_toggle', self.toggle)
            api.register_midi_action_handler('color_grade_next',   self.next_grade)
            api.register_midi_action_handler('color_grade_prev',   self.prev_grade)
        except Exception as exc:
            import logging  # noqa: PLC0415
            logging.getLogger(__name__).debug('color-grade-01: MIDI registration failed: %s', exc)
        # Control Room panel (docs/planning/control-room-drop-in-integration-
        # plan-2026-09-05.md, P1); guarded so an older core just gets no panel.
        register = getattr(api, 'register_operator_panel', None)
        if callable(register):
            try:
                from unicornviz.operator_panels import OperatorPanel  # noqa: PLC0415
                register(OperatorPanel(
                    name='color_grade',
                    title='Color Grade',
                    page='fx',
                    priority=120,
                    size='small',
                    content=self._operator_panel_content,
                    on_action=self._operator_panel_action,
                    tooltips={'toggle': 'Toggle the global color grade / LUT pass', 'prev': 'Previous look / LUT', 'next': 'Next look / LUT', 'int_down': 'Grade intensity down', 'int_up': 'Grade intensity up'},
                ))
            except Exception as exc:
                import logging  # noqa: PLC0415
                logging.getLogger(__name__).debug('color-grade-01: operator panel registration failed: %s', exc)

    def is_active(self) -> bool:
        """True when the pass should run (enabled, has visible effect)."""
        if not self.enabled or self._intensity <= 1e-3:
            return False
        return self._grades[self._index].name != 'Neutral'

    @property
    def active_name(self) -> str:
        return self._grades[self._index].name

    @property
    def intensity(self) -> float:
        return self._intensity

    def set_intensity(self, value: float) -> float:
        self._intensity = float(np.clip(value, 0.0, 1.0))
        return self._intensity

    # -- Configuration-editor convention -------------------------------------
    # Declares this controller's tunable settings so the core config editor can
    # list, adjust, and persist them without hard-coding drop-in knowledge.
    CONFIG_EDITOR_CATEGORY = 'Visuals'
    CONFIG_EDITOR_KEY = 'color_grade'

    def config_editor_settings(self) -> list[dict[str, float | str]]:
        """Return tunable settings as [{'name','value','min','max'}]."""
        return [
            {'name': 'intensity', 'value': float(self._intensity), 'min': 0.0, 'max': 1.0},
        ]

    def set_config_setting(self, name: str, value: float) -> None:
        """Apply a config-editor setting by name (live)."""
        if name == 'intensity':
            self.set_intensity(value)

    def _operator_panel_content(self) -> Any:
        """Control Room panel state -- CR render thread; property reads only."""
        from unicornviz.operator_panels import PanelButton, PanelContent, PanelMeter, PanelRow  # noqa: PLC0415
        on = bool(self.enabled)
        return PanelContent(
            status='ON' if on else 'OFF',
            rows=(PanelRow('Look', self.active_name, emphasis='accent' if self.is_active() else ''),),
            meters=(PanelMeter('Intensity', float(self._intensity), f'{float(self._intensity):.2f}'),),
            buttons=(
                PanelButton('toggle', 'TOGGLE', active=on),
                PanelButton('prev', 'PREV'),
                PanelButton('next', 'NEXT'),
                PanelButton('int_down', '-'),
                PanelButton('int_up', '+'),
            ),
        )

    def _operator_panel_action(self, action: str, _payload: Any) -> str | None:
        """Control Room buttons -> the same verbs and flash text as the hotkeys."""
        if action == 'toggle':
            on = self.toggle()
            return f'Color grade {"on" if on else "off"} ({self.active_name})'
        if action == 'next':
            return f'Grade: {self.next_grade()}'
        if action == 'prev':
            return f'Grade: {self.prev_grade()}'
        if action == 'int_up':
            return f'Grade intensity {self.set_intensity(self._intensity + 0.1):.2f}'
        if action == 'int_down':
            return f'Grade intensity {self.set_intensity(self._intensity - 0.1):.2f}'
        return None

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        return self.enabled

    def next_grade(self) -> str:
        self._index = (self._index + 1) % len(self._grades)
        return self.active_name

    def prev_grade(self) -> str:
        self._index = (self._index - 1) % len(self._grades)
        return self.active_name

    def select_grade(self, name: str) -> bool:
        for i, grade in enumerate(self._grades):
            if grade.name.lower() == str(name).lower():
                self._index = i
                return True
        return False

    @property
    def debug_summary(self) -> str:
        return f'en={int(self.enabled)} look={self.active_name} i={self._intensity:.2f}'

    # --------------------------------------------------------------- rendering
    def apply(
        self,
        src_tex: moderngl.Texture,
        dst_fbo: moderngl.Framebuffer,
        dt: float,            # noqa: ARG002 - shared post-chain signature
        bass: float,          # noqa: ARG002
        mid: float,           # noqa: ARG002
        treble: float,        # noqa: ARG002
        beat: float,          # noqa: ARG002
    ) -> bool:
        """Render the graded frame from ``src_tex`` into ``dst_fbo``."""
        if not self.is_active():
            return False
        grade = self._grades[self._index]
        dst_fbo.use()
        self._ctx.viewport = (0, 0, dst_fbo.size[0], dst_fbo.size[1])
        self._ctx.clear(0.0, 0.0, 0.0, 1.0)
        src_tex.use(location=0)
        self._prog['tex'].value = 0
        self._prog['uLut'].value = 1
        self._prog['uIntensity'].value = self._intensity

        if isinstance(grade, LutGrade):
            tex = self._lut_textures.get(self._index)
            if tex is None:
                return False
            tex.use(location=1)
            self._prog['uMode'].value = 1
            self._prog['uLutSize'].value = float(grade.size)
        else:
            # Keep the sampler3D complete with a dummy 3D texture on unit 1.
            self._dummy_lut.use(location=1)
            self._prog['uMode'].value = 0
            self._prog['uLutSize'].value = 2.0
            self._prog['uTemp'].value = grade.temp
            self._prog['uTint'].value = grade.tint
            self._prog['uLift'].value = tuple(grade.lift)
            self._prog['uGamma'].value = tuple(grade.gamma)
            self._prog['uGain'].value = tuple(grade.gain)
            self._prog['uSat'].value = grade.saturation
            self._prog['uContrast'].value = grade.contrast
        self._vao.render(moderngl.TRIANGLE_STRIP)
        return True

    def resize(self, width: int, height: int) -> None:
        # The pass reads dst_fbo.size each frame; nothing to rebuild.
        self._width = width
        self._height = height

    # ------------------------------------------------------------- input/teardown
    def handle_key(self, sym: int, mod: int) -> 'str | None | bool':
        """Handle Ctrl+Shift+Alt color-grade hotkeys; return status string when handled."""
        import sdl2  # noqa: PLC0415
        if not (
            (mod & sdl2.KMOD_CTRL)
            and (mod & sdl2.KMOD_ALT)
            and (mod & sdl2.KMOD_SHIFT)
        ):
            return False
        if sym == sdl2.SDLK_l:
            on = self.toggle()
            return f'Color grade {"on" if on else "off"} ({self.active_name})'
        if sym == sdl2.SDLK_PERIOD:
            return f'Grade: {self.next_grade()}'
        if sym == sdl2.SDLK_COMMA:
            return f'Grade: {self.prev_grade()}'
        if sym == sdl2.SDLK_SEMICOLON:
            return f'Grade intensity {self.set_intensity(self._intensity + 0.1):.2f}'
        if sym == sdl2.SDLK_QUOTE:
            return f'Grade intensity {self.set_intensity(self._intensity - 0.1):.2f}'
        return False

    def destroy(self) -> None:
        # Drop the Control Room panel first (operator_panels.py "Lifecycle").
        unregister = getattr(getattr(self, '_vj_api', None), 'unregister_operator_panel', None)
        if callable(unregister):
            try:
                unregister('color_grade')
            except Exception:
                pass
        try:
            self._vao.release()
            self._vbo.release()
            self._prog.release()
            self._dummy_lut.release()
            for tex in self._lut_textures.values():
                tex.release()
            self._lut_textures.clear()
        except Exception as exc:
            log.warning('color-grade: destroy error: %s', exc)
