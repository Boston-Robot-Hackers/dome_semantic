import os
import pathlib

import pytest


@pytest.fixture(autouse=True)
def set_repo_root_cwd():
    """Run every test with cwd = package root so relative paths like
    'examples/configs/class_profiles.yaml' resolve correctly."""
    repo_root = pathlib.Path(__file__).parent.parent
    original = os.getcwd()
    os.chdir(repo_root)
    yield
    os.chdir(original)
