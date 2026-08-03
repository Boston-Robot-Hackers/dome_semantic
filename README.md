# dome_semantic

Semantic map for the DOME robot: tracks confirmed object targets (two-tier
confirmation, label-constrained association) in the SLAM map frame. Neutral
package — depends only on `dome_semantic_msgs` and TF, so `dome_nav` never
depends on it and vice versa (F33).

## Installation

```bash
git clone <repo url>
cd dome_semantic
colcon build --packages-select dome_semantic
```

## Usage

Currently a pure Python core only (F33 T02) — no ROS node yet. The ROS shell
(publisher, TF handling, persistence) lands in later TF33 tasks.

## Development

```bash
/usr/bin/python3 -m pytest test/
```

## License

MIT — see [LICENSE](LICENSE)
