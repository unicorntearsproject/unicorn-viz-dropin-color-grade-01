# color-grade-01 — Global Color Grade / LUT Post Pass

**Version 0.9.0**


A single persistent post-process pass that sits in the global post-FX chain
(after postfx-01) and applies a colour grade to the whole frame — either a
built-in procedural "look" or a 3D LUT loaded from an Adobe `.cube` file —
blended against the source by an `intensity` mix.

## Controls

Hotkeys auto-register into the `H` help overlay via `HELP_ENTRIES`:

| Key | Action |
| --- | --- |
| `Ctrl+Shift+Alt+L` | Toggle global color grade on/off |
| `Ctrl+Shift+Alt+.` | Next look / LUT |
| `Ctrl+Shift+Alt+,` | Previous look / LUT |
| `Ctrl+Shift+Alt+;` | Intensity up |
| `Ctrl+Shift+Alt+'` | Intensity down |

## Configuration

```toml
[color_grade]
enabled = true            # load the drop-in (default true)
start_enabled = true      # apply the grade at boot (default true; passive pass)
intensity = 0.85          # 0–1 blend against the ungraded frame
default_grade = "random"  # built-in look name, LUT stem, or "random"
lut_dir = "assets/luts"   # dir of Adobe .cube 3D LUTs (this is the default)
```

Built-in looks: Neutral, Teal & Orange, Warm Sunset, Cool Night, Noir,
Vibrant Pop, Faded Film, Cyberpunk, Neon Rave, Acid Wash. The looks are bold by
design (stage/club grades over busy visuals); lower `intensity` to ease off.
Drop `.cube` files into `lut_dir` (defaults to the repo `assets/luts/`) to add
LUT looks; they appear in the cycle after the built-ins.

When `default_grade = "random"` (or unset) the pass starts on a random
non-neutral look, so two runs look distinct from frame 0 (per the project's
effect-randomization guideline).

## Integration

Runs through the app's shared global post chain
(`App._apply_post_chain`), exposing the same contract as postfx-01:
`apply(src_tex, dst_fbo, dt, bass, mid, treble, beat)`. It writes directly into
the destination FBO (reading its size for the viewport), so it needs no
internal render target. Registered as the `color_grade` subsystem.

## Dependencies

Core only: `moderngl`, `numpy` (LUT parsing). No new dependencies.

## Troubleshooting

- **No visible change:** confirm `start_enabled = true` (or toggle on with
  `Ctrl+Shift+Alt+L`), `intensity > 0`, and the active look is not `Neutral`
  (the pass is skipped when neutral).
- **LUT not appearing:** ensure files end in `.cube`, contain `LUT_3D_SIZE`,
  and live in `lut_dir`. 1D `.cube` LUTs are not supported.

See `docs/` for operations, configuration, integration, and troubleshooting.

## Changelog

- **0.9.0** — Control Room panel (P1 of `docs/planning/control-room-drop-in-integration-plan-2026-09-05.md`): registered on the shared **FX** page from `set_vj_api()` — active look, intensity meter, TOGGLE / PREV / NEXT / − / + buttons calling the same `toggle()` / `prev_grade()` / `next_grade()` / `set_intensity()` as the `Ctrl+Shift+Alt+L/,/./;/'` hotkeys and flashing the same text. Unregistered in `destroy()`.
- **0.8.0** — initial versioned release.
