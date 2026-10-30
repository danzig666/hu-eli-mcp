#!/usr/bin/env python3
"""Build the njt-jogszabalyok Claude skill as an uploadable ZIP, with hu-eli bundled.

The skill runs the hu-eli CLI from its own vendor/ folder, so a Claude chat never has to
download code from GitHub. This script fills vendor/ from a commit of this repository
(git archive: src/, pyproject.toml, LICENSE) and zips the skill folder.

Run from anywhere inside a clone (needs git and Python 3.11+, any OS):

    python skills/build_skill.py                 # bundle HEAD -> dist/njt-jogszabalyok.zip
    python skills/build_skill.py --commit <rev>  # bundle another commit, branch or tag
    python skills/build_skill.py --out my.zip

The working tree is not modified: the skill is assembled in a temporary folder. Upload the
ZIP as a skill in Claude (Settings > Capabilities > Skills) or ship it in a plugin.
"""
from __future__ import annotations

import argparse
import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

SKILL = "njt-jogszabalyok"
HERE = os.path.dirname(os.path.abspath(__file__))
VENDORED = ["src", "pyproject.toml", "LICENSE"]
EXCLUDE_PARTS = {"__pycache__", "tests", "test"}


def git(*args: str, cwd: str) -> bytes:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True).stdout


def build(commit: str, out: str) -> str:
    root = git("rev-parse", "--show-toplevel", cwd=HERE).decode().strip()
    sha = git("rev-parse", "--verify", f"{commit}^{{commit}}", cwd=root).decode().strip()
    remote = ""
    try:
        remote = git("remote", "get-url", "origin", cwd=root).decode().strip()
    except subprocess.CalledProcessError:
        pass

    skill_src = os.path.join(root, "skills", SKILL)
    for need in ("SKILL.md", os.path.join("scripts", "hu_eli.py")):
        if not os.path.isfile(os.path.join(skill_src, need)):
            sys.exit(f"missing {os.path.join(skill_src, need)}")

    with tempfile.TemporaryDirectory() as tmp:
        skill = os.path.join(tmp, SKILL)
        shutil.copytree(skill_src, skill,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "vendor"))
        vendor = os.path.join(skill, "vendor")
        os.makedirs(vendor)

        archive = git("archive", "--format=tar", sha, *VENDORED, cwd=root)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            members = [m for m in tar.getmembers()
                       if not EXCLUDE_PARTS.intersection(m.name.split("/"))]
            try:
                tar.extractall(vendor, members=members, filter="data")
            except TypeError:  # Python before 3.11.4: no extraction filters
                tar.extractall(vendor, members=members)
        if not os.path.isdir(os.path.join(vendor, "src", "hu_eli_mcp")):
            sys.exit(f"{sha} has no src/hu_eli_mcp: not a hu-eli-mcp commit with the CLI")

        with open(os.path.join(vendor, "VERSION"), "w", encoding="utf-8") as f:
            f.write(f"{sha}\n{remote}\n")

        # Same check the skill runs first in a chat; missing dependencies are reported,
        # not fatal here (the chat installs them from PyPI).
        subprocess.run([sys.executable, os.path.join(skill, "scripts", "hu_eli.py"),
                        "--selfcheck"])

        out = os.path.abspath(out)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        if os.path.exists(out):
            os.remove(out)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for base, dirs, files in os.walk(skill):
                dirs[:] = sorted(d for d in dirs if d != "__pycache__")
                for fn in sorted(files):
                    if fn.endswith(".pyc"):
                        continue
                    full = os.path.join(base, fn)
                    z.write(full, os.path.relpath(full, tmp).replace(os.sep, "/"))
    print(f"bundled hu-eli @ {sha}")
    print(f"ready: {out}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--commit", default="HEAD", help="commit, branch or tag to bundle")
    ap.add_argument("--out", default=None, help="ZIP path (default: dist/njt-jogszabalyok.zip)")
    a = ap.parse_args()
    root = git("rev-parse", "--show-toplevel", cwd=HERE).decode().strip()
    build(a.commit, a.out or os.path.join(root, "dist", f"{SKILL}.zip"))


if __name__ == "__main__":
    main()
