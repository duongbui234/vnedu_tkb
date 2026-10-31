"""Distribution artifacts must never carry local research or API collections."""

import tarfile
import zipfile
from pathlib import Path

import pytest
from hatchling.build import build_sdist, build_wheel


def test_build_excludes_research_and_private_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Call the PEP 517 hooks of the pinned build backend directly: the backend alone decides
    # artifact contents, and no uv binary, package cache or network is involved.
    monkeypatch.chdir(Path(__file__).resolve().parents[2])
    build_sdist(str(tmp_path))
    build_wheel(str(tmp_path))
    allowed = {
        "src",
        "tests",
        "README.md",
        "pyproject.toml",
        "uv.lock",
        ".python-version",
        ".gitignore",  # Hatchling always includes VCS ignore metadata in sdists.
        "PKG-INFO",
    }
    with tarfile.open(next(tmp_path.glob("*.tar.gz"))) as archive:
        names = {m.name.split("/", 1)[1] for m in archive.getmembers() if m.isfile()}
        assert {"pyproject.toml", "src/tkb_core/__init__.py"} <= names
        for member in archive.getmembers():
            if not member.isfile():
                continue
            relative = member.name.split("/", 1)[1]
            assert relative.split("/")[0] in allowed or relative in {
                "docs/assumptions.md",
                "docs/domain-model.md",
                "docs/solver-design.md",
                "docs/constraint-catalog.md",
                "docs/phase-1-report.md",
                "docs/phase-2a-report.md",
            }, relative
    with zipfile.ZipFile(next(tmp_path.glob("*.whl"))) as wheel:
        assert "tkb_core/solver/objectives.py" in wheel.namelist()
        for name in wheel.namelist():
            assert name.startswith("tkb_core/") or ".dist-info/" in name, name
