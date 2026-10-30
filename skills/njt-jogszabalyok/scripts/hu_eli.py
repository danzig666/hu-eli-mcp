#!/usr/bin/env python3
"""Launcher for the hu-eli CLI bundled in this skill (vendor/).

Nothing is downloaded or installed here. The entry point and the dependency list are
read from vendor/pyproject.toml, so the launcher does not need to know the package name.

    python3 hu_eli.py --selfcheck           check the bundle and the dependencies
    python3 hu_eli.py local Debrecen 2020 47 --search "Lke-J/4"

Environment override: HU_ELI_ENTRY="package.module:function" if pyproject.toml has no
[project.scripts] entry for "hu-eli".
"""
from __future__ import annotations

import importlib
import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(os.path.dirname(HERE), "vendor")
PYPROJECT = os.path.join(VENDOR, "pyproject.toml")

# hu_eli_mcp.runtime would fetch a config manifest from the upstream GitHub release on
# first use; the bundle runs on the pinned commit's built-in defaults instead.
# Set HU_ELI_RUNTIME_URL explicitly to re-enable it.
os.environ.setdefault("HU_ELI_RUNTIME_URL", "")

# src layout first, then flat layout, then optional pre-bundled pure-Python dependencies
for _p in (os.path.join(VENDOR, "_deps"), VENDOR, os.path.join(VENDOR, "src")):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)


def fail(msg: str, code: int = 2) -> None:
    print(f"[hu-eli launcher] {msg}", file=sys.stderr)
    sys.exit(code)


def load_pyproject() -> dict:
    if not os.path.isfile(PYPROJECT):
        fail(f"missing {PYPROJECT}: the bundled hu-eli source is not in the skill folder")
    try:
        import tomllib  # Python 3.11+
    except ModuleNotFoundError:
        fail("Python 3.11 or newer is needed to read pyproject.toml")
    with open(PYPROJECT, "rb") as f:
        return tomllib.load(f)


def entry_point(meta: dict) -> str:
    env = os.environ.get("HU_ELI_ENTRY")
    if env:
        return env
    scripts = meta.get("project", {}).get("scripts", {}) or {}
    if "hu-eli" in scripts:
        return scripts["hu-eli"]
    if len(scripts) == 1:
        return next(iter(scripts.values()))
    fail("no 'hu-eli' entry in [project.scripts] of vendor/pyproject.toml; "
         f"found: {sorted(scripts) or 'none'}. Set HU_ELI_ENTRY=module:function")
    return ""  # unreachable


def missing_dependencies(meta: dict) -> list[str]:
    from importlib import metadata

    missing = []
    for req in meta.get("project", {}).get("dependencies", []) or []:
        # skip requirements whose environment marker excludes this interpreter
        if ";" in req:
            try:
                from packaging.markers import Marker  # type: ignore

                if not Marker(req.split(";", 1)[1]).evaluate():
                    continue
            except Exception:
                pass
        m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", req)
        if not m:
            continue
        try:
            metadata.distribution(m.group(1))
        except metadata.PackageNotFoundError:
            # also accept a copy bundled in vendor/_deps without dist-info
            mod = m.group(1).replace("-", "_").lower()
            if importlib.util.find_spec(mod) is None:
                missing.append(req.split(";", 1)[0].strip())
    return missing


def install_hint(missing: list[str]) -> str:
    quoted = " ".join(f'"{r}"' for r in missing)
    return f"pip install --break-system-packages -q {quoted}"


def version() -> str:
    try:
        with open(os.path.join(VENDOR, "VERSION"), encoding="utf-8") as f:
            return f.readline().strip() or "unknown"
    except OSError:
        return "unknown"


def main() -> None:
    meta = load_pyproject()
    target = entry_point(meta)
    missing = missing_dependencies(meta)

    if sys.argv[1:2] == ["--selfcheck"]:
        print(f"bundle: {VENDOR} (commit {version()})")
        print(f"entry point: {target}")
        if missing:
            print("missing dependencies (from PyPI, names from vendor/pyproject.toml):")
            print("  " + install_hint(missing))
            sys.exit(3)
        mod_name = target.split(":", 1)[0]
        try:
            importlib.import_module(mod_name)
        except Exception as e:  # noqa: BLE001
            fail(f"cannot import {mod_name}: {e!r}", 4)
        print("OK")
        return

    if missing:
        fail("missing dependencies; run once, then retry:\n  " + install_hint(missing), 3)

    mod_name, _, func_name = target.partition(":")
    try:
        mod = importlib.import_module(mod_name)
    except ModuleNotFoundError as e:
        fail(f"cannot import {mod_name}: {e}. Check the vendor/ folder.", 4)
    func = mod
    for part in (func_name or "main").split("."):
        func = getattr(func, part)

    sys.argv[0] = "hu-eli"
    result = func()
    if isinstance(result, int):
        sys.exit(result)


if __name__ == "__main__":
    main()
