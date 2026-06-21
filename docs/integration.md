# color-grade-01 Integration

Owner: Drop-in Maintainers
Status: active
Last updated: 2026-06-21

## Load path

`app.py` loads the controller via `_load_color_grade_controller_class()` →
`load_dropin_symbol('color-grade-01/color_grade_controller.py',
'ColorGradeController')` inside a `try/except` that sets `self._color_grade =
None` on failure. The app starts cleanly when the drop-in is absent.

## Global post chain

The app composes global post passes through two helpers:

- `App._active_post_chain()` returns the ordered list of active controllers:
  `postfx → color_grade` (beat-flash-01 appends itself here in its own
  increment). Each exposes `is_active()` and the shared `apply(src_tex,
  dst_fbo, dt, bass, mid, treble, beat)` contract.
- `App._apply_post_chain(dt)` runs each active pass `fbo_a → fbo_b` and blits
  back into `fbo_a`, so the chained result always ends in `fbo_a`.

This replaced the previously-inlined postfx-only apply blocks at the four
composite sites, so any number of global post passes compose uniformly across
single, mirror, and transition display paths.

## Runtime surface

Registered as the `color_grade` subsystem. Reachable via
`vj_api.get_subsystem('color_grade')`:

- `toggle()`, `next_grade()`, `prev_grade()`, `select_grade(name)`
- `set_intensity(value)`, `intensity`, `active_name`, `is_active()`

The OSC bridge (osc-bridge-01) maps `/uv/colorgrade/intensity` and
`/uv/colorgrade/next` to these.

## Independence

Self-contained: it defines its own fullscreen quad + shader (no dependency on
postfx-01's base). Excluding it leaves the post chain working with postfx only.
