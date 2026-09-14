"""Ensure ovro-alert packaging stays installable on Python 3.6."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

try:
    from packaging.specifiers import SpecifierSet
except ImportError:  # pragma: no cover
    SpecifierSet = None  # type: ignore[misc, assignment]

ROOT = Path(__file__).resolve().parents[1]
_PYPROJECT = ROOT / "pyproject.toml"
_SETUP_PY = ROOT / "setup.py"


def _section_lines(name: str) -> list[str]:
    lines = _PYPROJECT.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    in_section = False
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            in_section = line == f"[{name}]"
            continue
        if in_section:
            if line.startswith("["):
                break
            out.append(line)
    return out


def _quoted_list_value(line: str) -> list[str]:
    return re.findall(r'"([^"]+)"', line)


def test_setup_py_requires_python_includes_36():
    text = _SETUP_PY.read_text(encoding="utf-8")
    match = re.search(r'python_requires\s*=\s*"([^"]+)"', text)
    assert match is not None, "python_requires missing from setup.py"
    assert match.group(1) == ">=3.6"


@pytest.mark.skipif(SpecifierSet is None, reason="packaging not installed")
def test_requires_python_allows_python_36():
    text = _SETUP_PY.read_text(encoding="utf-8")
    match = re.search(r'python_requires\s*=\s*"([^"]+)"', text)
    spec = SpecifierSet(match.group(1))
    assert spec.contains("3.6")
    assert spec.contains("3.6.0")
    assert spec.contains("3.9")
    assert spec.contains(sys.version.split()[0])


def test_build_system_requires_setuptools_compatible_with_python36():
    section = "\n".join(_section_lines("build-system"))
    requires_line = next(
        (line for line in section.splitlines() if line.strip().startswith("requires")),
        "",
    )
    requires = _quoted_list_value(requires_line)
    assert any(r.startswith("setuptools>") or r.startswith("setuptools=") for r in requires)
    assert any("setuptools_scm" in r for r in requires)
    for req in requires:
        if req.startswith("setuptools") and "setuptools_scm" not in req:
            assert "<60" in req, f"setuptools must stay <60 for Python 3.6: {req}"
            assert ">=61" not in req
        if "setuptools_scm" in req:
            assert "<8" in req, f"setuptools_scm must stay <8 for Python 3.6: {req}"


def _bootstrap_pip_for_python36(py36: str) -> bool:
    """Return True if pip>=21 is available for python3.6."""
    probe = subprocess.run(
        [py36, "-m", "pip", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        return False
    version = probe.stdout.split()[1]
    major, minor = (int(x) for x in version.split(".")[:2])
    if (major, minor) >= (21, 0):
        return True
    boot = subprocess.run(
        [py36, "-m", "pip", "install", "--user", "-q", "pip>=21,<22"],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    return boot.returncode == 0


@pytest.mark.skipif(not shutil.which("python3.6"), reason="python3.6 not on PATH")
def test_pip_install_succeeds_on_python_36():
    """PEP 517 build deps must resolve on Python 3.6 (deployment env)."""
    py36 = shutil.which("python3.6")
    assert py36 is not None

    if not _bootstrap_pip_for_python36(py36):
        pytest.skip("could not run or upgrade pip on python3.6 (network required)")

    proc = subprocess.run(
        [py36, "-m", "pip", "install", "--user", "--no-cache-dir", "."],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    combined = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, (
        "expected pip install to succeed on Python 3.6; got failure:\n" + combined
    )
    assert "setuptools>=61" not in combined
