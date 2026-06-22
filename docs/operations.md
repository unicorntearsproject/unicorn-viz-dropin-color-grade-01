# color-grade-01 Operations

Owner: Drop-in Maintainers
Status: active
Last updated: 2026-06-21

## Purpose

Apply a global colour grade (procedural look or 3D LUT) to the final frame as a
persistent pass in the global post-FX chain.

## Lifecycle

- Loaded by `app.py` during GL setup (after postfx) when the drop-in is present.
- Registered as the `color_grade` subsystem + key handler.
- Driven each frame via `App._apply_post_chain` when `is_active()` is true.
- Released via `destroy()` at shutdown.

## Live operation

- `Ctrl+Shift+Alt+L` — toggle the grade on/off.
- `Ctrl+Shift+Alt+.` / `Ctrl+Shift+Alt+,` — cycle looks/LUTs forward/back.
- `Ctrl+Shift+Alt+;` / `Ctrl+Shift+Alt+'` — intensity up/down.

The pass is skipped (no GPU cost) when disabled, when intensity is 0, or when
the active look is `Neutral`.
