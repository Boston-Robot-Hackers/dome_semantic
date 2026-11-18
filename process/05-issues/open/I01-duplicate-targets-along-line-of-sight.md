# I01 Range noise makes duplicate targets along one line of sight

Raised 2026-11-17 on a bench run, while checking F05's launch rename in
`dome2`.

## Symptom

The robot sat still with two cans in view at **~5 m**. The semantic map
held **five can targets**:

| Target | Map (x, y) m | Range m | Observations |
|---|---|---|---|
| T1 | (4.17, −1.66) | 4.49 | 519 |
| T7 | (3.28, −1.30) | 3.53 | 53 |
| T18 | (4.99, −2.00) | 5.38 | 31 |
| T39 | (11.5, −4.68) | 12.4 | 9 |
| T2 | (2.98, 0.85) | 3.10 | 94 |

- **T1, T7, T18 and T39 lie on one line from the robot** (y/x ≈ −0.40).
  They are all one can. T1 is the real one.
- **T2 is the second can,** placed about 2 m short.
- `map → odom` was the identity (`--static_map_odom true`), and the robot
  never moved, so the pose is not the cause.

## What has been checked

- **The input is the cause.** `/oak/detections_3d` gave the strong can's
  range in whole-pixel disparity steps, from 2.85 m to 34.2 m. The detail is
  in `dome_vision` I04.
- The tracker did what it is built to do. A detection outside the
  association radius of every existing target starts a new one.

## Theory

- **The main fix belongs in `dome_vision` I04**, as F36's run already
  concluded: no association radius should absorb errors this large.
- **The tracker could still help, separately.** Stereo range error grows
  with the square of the range, while bearing stays good. Two options:
  - a gate that is longer along the line of sight than across it, scaled
    by range
  - a max-range gate for small classes
- **Not decided.** First see what `dome_vision` can fix at the source.
