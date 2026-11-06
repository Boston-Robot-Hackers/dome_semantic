#!/usr/bin/env python3
# test_power_load_test — the power load test's report, preflight and arguments
# Author: Pito Salas and Claude Code
# Open Source Under MIT license

"""Runs tools/power_load_test.sh as a subprocess on fixture run directories.

The load stages themselves start real hardware, so only the parts that work
off the robot are tested here: `--report` (the per-stage summary from
tools/power_summary.awk), the preflight's workspace check, and argument
errors. The stages are checked by the manual hardware run (TF35.5).
"""

import pathlib
import subprocess

SCRIPT = pathlib.Path(__file__).parent.parent / "tools" / "power_load_test.sh"

RAIL_LOG = """\
2026-11-05 10:00:00.000 idle 5.10 0x0
2026-11-05 10:00:00.200 idle 5.00 0x0
2026-11-05 10:00:01.000 oak 4.70 0x50005
2026-11-05 10:00:01.200 oak 4.90 0x50000
"""

KERNEL_LOG = """\
2026-11-05 10:00:01.100 oak Nov 05 10:00:01 dome-R1 kernel: hwmon hwmon2: \
Undervoltage detected!
2026-11-05 10:00:01.150 oak Nov 05 10:00:01 dome-R1 kernel: usb 4-1: \
USB disconnect, device number 3
"""

WIFI_LOG = """\
2026-11-05 10:00:00.500 idle 3.2
2026-11-05 10:00:01.500 oak lost
2026-11-05 10:00:01.900 oak 45.5
"""

STAGE_INFO_LOG = "2026-11-05 10:00:01.300 oak pack_v=11.80 power_w=12.5 oak_usb=480M\n"


def run_script(
    *args: str, cwd: pathlib.Path | None = None
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def make_run_dir(tmp_path: pathlib.Path, rail_log: str = RAIL_LOG) -> pathlib.Path:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "rail.log").write_text(rail_log)
    (run_dir / "kernel.log").write_text(KERNEL_LOG)
    (run_dir / "wifi.log").write_text(WIFI_LOG)
    (run_dir / "stage_info.log").write_text(STAGE_INFO_LOG)
    return run_dir


def stage_block(report: str, stage: str) -> str:
    """The lines of one stage's block in a report."""
    blocks = report.split("== ")
    return next(block for block in blocks if block.startswith(f"{stage} =="))


def test_script_syntax_is_valid():
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_report_summarizes_each_stage_in_order(tmp_path):
    result = run_script("--report", str(make_run_dir(tmp_path)))
    assert result.returncode == 0, result.stderr
    assert result.stdout.index("== idle ==") < result.stdout.index("== oak ==")
    idle = stage_block(result.stdout, "idle")
    assert "min 5.00 V, mean 5.05 V, 0 below 4.80 V (2 samples)" in idle
    assert "0 undervoltage, 0 USB disconnect" in idle
    assert "worst 3.2 ms, 0 of 1 lost" in idle


def test_report_counts_dips_events_and_throttle_changes(tmp_path):
    result = run_script("--report", str(make_run_dir(tmp_path)))
    oak = stage_block(result.stdout, "oak")
    assert "min 4.70 V, mean 4.80 V, 1 below 4.80 V (2 samples)" in oak
    assert "0x50000 at end, 2 change(s)" in oak
    assert "1 undervoltage, 1 USB disconnect" in oak
    assert "worst 45.5 ms, 1 of 2 lost" in oak
    assert "pack_v=11.80 power_w=12.5 oak_usb=480M" in oak


def test_report_skips_a_line_cut_off_by_a_crash(tmp_path):
    rail_log = RAIL_LOG + "2026-11-05 10:00:01.400 oak 4.6"
    result = run_script("--report", str(make_run_dir(tmp_path, rail_log)))
    assert result.returncode == 0, result.stderr
    assert "min 4.70 V" in stage_block(result.stdout, "oak")


def test_report_on_a_missing_run_dir_fails(tmp_path):
    result = run_script("--report", str(tmp_path / "nope"))
    assert result.returncode != 0
    assert "not a power test run directory" in result.stderr


def test_preflight_fails_outside_a_workspace(tmp_path):
    result = run_script(cwd=tmp_path)
    assert result.returncode != 0
    assert "run from the workspace root" in result.stderr


def test_bad_hold_value_fails():
    result = run_script("--hold", "0")
    assert result.returncode != 0
    assert "--hold" in result.stderr
