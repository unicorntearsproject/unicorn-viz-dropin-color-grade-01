# color-grade-01 Troubleshooting

Owner: Drop-in Maintainers
Status: active
Last updated: 2026-06-21

## No visible grade

- Confirm `[color_grade] start_enabled = true` (or toggle on with
  `Ctrl+Shift+Alt+L`) and `intensity > 0`.
- The active look may be `Neutral` (the pass is intentionally skipped). Cycle
  with `Ctrl+Shift+Alt+.`.

## Frame goes black when grading

This was a real regression: a `sampler3D` (`uLut`) left on the default texture
unit (where the 2D source lives) is an *incomplete* sampler and renders the
whole frame black even in procedural mode. The controller now always binds a
1³ dummy 3D texture to the LUT unit in procedural mode to keep the sampler
complete. If you modify the shader, preserve that invariant.

## LUT not loading

- File must end in `.cube` and include a `LUT_3D_SIZE` line.
- 1D LUTs (`LUT_1D_SIZE`) are unsupported and rejected.
- Entry count must equal `size³`; malformed files are skipped with a warning.

## Colours look wrong with a LUT

- The shader applies texel-centre correction `(c*(N-1)+0.5)/N`. Very small LUTs
  (size 2) are coarse by nature; use a 17/33-size `.cube` for smooth grades.

## Tests

`tests/test_grades.py` covers `.cube` parsing without GL. `tests/test_controller.py`
exercises the GL pass and skips automatically when no headless context is
available.
