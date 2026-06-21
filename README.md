# color-grade-01 — Global Color Grade / LUT Post Pass

A single persistent post-process pass that sits in the global post-FX chain
(after postfx-01) and applies a colour grade to the whole frame — either a
built-in procedural "look" or a 3D LUT loaded from an Adobe `.cube` file —
blended against the source by an `intensity` mix.

## Controls

Hotkeys auto-register into the `H` help overlay via `HELP_ENTRIES`:

| Key | Action |
| --- | --- |
| `Ctrl+Alt+L` | Toggle global color grade on/off |
| `Ctrl+Alt+.` | Next look / LUT |
| `Ctrl+Alt+,` | Previous look / LUT |
| `Ctrl+Alt+;` | Intensity up |
| `Ctrl+Alt+'` | Intensity down |

## Configuration

```toml
[color_grade]
enabled = true
intensity = 0.85          # 0–1 blend against the ungraded frame
default_grade = "random"  # built-in look name, LUT stem, or "random"
lut_dir = "assets/luts"   # optional dir of Adobe .cube 3D LUTs
```

Built-in looks: Neutral, Teal & Orange, Warm Sunset, Cool Night, Noir,
Vibrant Pop, Faded Film, Cyberpunk. Drop `.cube` files into `lut_dir` to add
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

- **No visible change:** confirm `enabled = true`, `intensity > 0`, and the
  active look is not `Neutral` (the pass is skipped when neutral).
- **LUT not appearing:** ensure files end in `.cube`, contain `LUT_3D_SIZE`,
  and live in `lut_dir`. 1D `.cube` LUTs are not supported.

See `docs/` for operations, configuration, integration, and troubleshooting.
