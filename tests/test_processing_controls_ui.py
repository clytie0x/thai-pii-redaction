"""Run the processing-control DOM workflows with the existing locked JS toolchain."""

import shutil
import subprocess
from pathlib import Path

import pytest


def test_processing_controls_staff_workflows():
    root = Path(__file__).resolve().parents[1]
    node = shutil.which("node")
    runner = root / "node_modules/vitest/vitest.mjs"
    if not node or not runner.is_file():
        pytest.skip("optional locked Node/Vitest toolchain unavailable")
    result = subprocess.run(
        [
            node,
            str(runner),
            "run",
            "tests/enterprise/processing_controls_ui.test.js",
            "--reporter=dot",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
