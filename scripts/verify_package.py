"""Verify that setuptools discovers the importable ``src`` package."""

from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
from setuptools.discovery import PackageFinder, PEP420PackageFinder

cfg = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
find_cfg = cfg["tool"]["setuptools"]["packages"]["find"]

where = find_cfg.get("where", ["."])
include = find_cfg.get("include", ["*"])
exclude = find_cfg.get("exclude", [])
finder = PEP420PackageFinder if find_cfg.get("namespaces", True) else PackageFinder

print(f"configured where: {where}")
print(f"configured include: {include}")

packages = sorted(
    {package for root in where for package in finder.find(root, include=include, exclude=exclude)}
)
top_level = sorted({package.split(".", 1)[0] for package in packages})

print(f"would-discover: {packages}")
print(f"top_level: {top_level}")

if top_level != ["src"] or "src.generators" not in packages:
    raise SystemExit("setuptools configuration does not install the expected src package")
