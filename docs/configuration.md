# color-grade-01 Configuration

Owner: Drop-in Maintainers
Status: active
Last updated: 2026-06-21

Keys live under `[color_grade]` in `config.toml`. All have safe defaults.

| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `enabled` | bool | `true` | Load the drop-in at all |
| `start_enabled` | bool | `false` | Apply the grade at boot; off by default since 0.10.0 (toggle live with Ctrl+Shift+Alt+L) |
| `intensity` | float | `0.85` | Blend against ungraded frame, `0–1` |
| `default_grade` | str | `random` | Built-in look name, LUT file stem, or `random` |
| `lut_dir` | str | `assets/luts` | Directory of Adobe `.cube` 3D LUTs (relative to app root) |

Built-in looks: `Neutral`, `Teal & Orange`, `Warm Sunset`, `Cool Night`,
`Noir`, `Vibrant Pop`, `Faded Film`, `Cyberpunk`, `Neon Rave`, `Acid Wash`.

LUTs: any `*.cube` file with a `LUT_3D_SIZE` header (red varies fastest, Adobe
order). 1D LUTs are rejected. Each LUT's file stem becomes its display name and
is appended to the look cycle after the built-ins.

Validation: `config_validator.py` flags non-boolean `enabled`/`start_enabled`,
out-of-range `intensity`, and non-string `lut_dir`/`default_grade`.

A documented copy lives in `config.full.example.toml`.
