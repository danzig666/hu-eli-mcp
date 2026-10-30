"""The njt-jogszabalyok Claude skill: the ZIP builds from this repo and its launcher runs.

Offline. Needs git (the build bundles a commit with `git archive`).
"""

from __future__ import annotations

import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "skills" / "build_skill.py"

pytestmark = pytest.mark.skipif(
    subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True).returncode,
    reason="not a git checkout",
)


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    tmp = tmp_path_factory.mktemp("skill")
    zip_path = tmp / "njt-jogszabalyok.zip"
    subprocess.run([sys.executable, str(BUILD), "--out", str(zip_path)], check=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(tmp / "x")
    return zip_path, tmp / "x" / "njt-jogszabalyok"


def test_zip_layout(built: tuple[Path, Path]) -> None:
    zip_path, _ = built
    names = set(zipfile.ZipFile(zip_path).namelist())
    for required in (
        "njt-jogszabalyok/SKILL.md",
        "njt-jogszabalyok/scripts/hu_eli.py",
        "njt-jogszabalyok/vendor/pyproject.toml",
        "njt-jogszabalyok/vendor/VERSION",
        "njt-jogszabalyok/vendor/LICENSE",
        "njt-jogszabalyok/vendor/src/hu_eli_mcp/cli.py",
        "njt-jogszabalyok/vendor/src/hu_eli_mcp/server.py",
    ):
        assert required in names, required
    assert not any("/tests/" in n or "__pycache__" in n for n in names)


def test_skill_md_never_installs_from_github(built: tuple[Path, Path]) -> None:
    _, skill = built
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\nname: \"njt-jogszabalyok\"")
    assert "archive/" not in text and "git+" not in text


def test_launcher_selfcheck(built: tuple[Path, Path]) -> None:
    _, skill = built
    env = {k: v for k, v in os.environ.items() if k != "HU_ELI_RUNTIME_URL"}
    r = subprocess.run(
        [sys.executable, str(skill / "scripts" / "hu_eli.py"), "--selfcheck"],
        capture_output=True, text=True, env=env,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "entry point: hu_eli_mcp.cli:main" in r.stdout
    assert r.stdout.rstrip().endswith("OK")


def test_launcher_runs_bundled_cli(built: tuple[Path, Path]) -> None:
    _, skill = built
    r = subprocess.run(
        [sys.executable, str(skill / "scripts" / "hu_eli.py"), "--help"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    assert "municipality" in r.stdout and "local" in r.stdout and "law" in r.stdout
