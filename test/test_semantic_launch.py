#!/usr/bin/env python3
# test_semantic_launch — semantic.launch.py wiring, checked against a fake BetterLaunch
# Author: Pito Salas and Claude Code
# Open Source Under MIT license

"""Runs the launch function against a fake BetterLaunch, so no process starts.

The @launch_this decorator launches immediately on import, so it is stripped
from the source before exec.
"""

import importlib.util
import inspect
import pathlib
from unittest.mock import MagicMock

import pytest
from better_launch.utils.click import DeclaredArg, get_click_options

LAUNCH_FILE = pathlib.Path(__file__).parent.parent / "launch" / "semantic.launch.py"


def load_launch_function(fake_bl: MagicMock | None = None):
    src = LAUNCH_FILE.read_text().replace("@launch_this(ui=True)", "")
    spec = importlib.util.spec_from_loader("semantic_launch_file", loader=None)
    module = importlib.util.module_from_spec(spec)
    # Launch files are scripts, not importable modules.
    exec(compile(src, str(LAUNCH_FILE), "exec"), module.__dict__)  # noqa: S102
    if fake_bl is not None:
        module.__dict__["BetterLaunch"] = fake_bl
    return module.__dict__["semantic_launch"]


def launched_nodes(**launch_args) -> dict[str, dict]:
    """Return {node name: bl.node kwargs} for one run of the launch function."""
    fake_bl = MagicMock()
    load_launch_function(fake_bl)(**launch_args)
    node_calls = fake_bl.return_value.node.call_args_list
    return {call.kwargs["name"]: call.kwargs for call in node_calls}


def test_args_build_click_options():
    func = load_launch_function()
    declared = [
        DeclaredArg(name=name, ptype=param.annotation, default=param.default)
        for name, param in inspect.signature(func).parameters.items()
    ]
    get_click_options(declared)


def test_map_name_is_required():
    with pytest.raises(ValueError, match="map_name is required"):
        launched_nodes()


def test_node_gets_passed_params():
    nodes = launched_nodes(map_name="kitchen", publish_every_n=3)
    expected = {"map_name": "kitchen", "publish_every_n": 3}
    assert nodes["semantic_map"]["params"] == expected


def test_static_map_odom_off_by_default():
    assert set(launched_nodes(map_name="kitchen")) == {"semantic_map"}


def test_static_map_odom_publishes_identity_map_to_odom():
    nodes = launched_nodes(map_name="kitchen", static_map_odom=True)
    assert nodes["map_odom_identity"]["cmd_args"] == [
        "--frame-id",
        "map",
        "--child-frame-id",
        "odom",
    ]
