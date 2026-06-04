"""Ensure ovro-alert cannot be built or installed on Python 3.6."""

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


def test_pyproject_declares_requires_python_at_least_39():
    section = "\n".join(_section_lines("project"))
    match = re.search(r'^requires-python\s*=\s*"([^"]+)"', section, re.MULTILINE)
    assert match is not None, "project.requires-python missing from pyproject.toml"
    assert match.group(1) == ">=3.9"


@pytest.mark.skipif(SpecifierSet is None, reason="packaging not installed")
def test_requires_python_excludes_python_36():
    section = "\n".join(_section_lines("project"))
    match = re.search(r'^requires-python\s*=\s*"([^"]+)"', section, re.MULTILINE)
    spec = SpecifierSet(match.group(1))
    assert not spec.contains("3.6")
    assert not spec.contains("3.6.0")
    assert spec.contains("3.9")
    assert spec.contains(sys.version.split()[0])


def test_build_system_requires_modern_setuptools():
    section = "\n".join(_section_lines("build-system"))
    requires = _quoted_list_value(section)
    assert "setuptools>=61" in requires
    assert "setuptools_scm>=8" in requires


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
def test_pip_install_fails_on_python_36():
    """PEP 517 build deps (setuptools>=61) are not available for Python 3.6."""
    py36 = shutil.which("python3.6")
    assert py36 is not None

    if not _bootstrap_pip_for_python36(py36):
        pytest.skip("could not run or upgrade pip on python3.6 (network required)")

    proc = subprocess.run(
        [py36, "-m", "pip", "install", "--user", "--no-cache-dir", "."],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    combined = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode != 0, (
        "expected pip install to fail on Python 3.6; got success:\n" + combined
    )
    assert "setuptools>=61" in combined or "No matching distribution found" in combined, (
        "expected build-system setuptools>=61 failure on Python 3.6:\n" + combined
    )
