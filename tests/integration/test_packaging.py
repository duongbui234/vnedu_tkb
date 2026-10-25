"""Distribution artifacts must never carry local research or API collections."""

import subprocess
import tarfile
import zipfile
from pathlib import Path


def test_build_excludes_research_and_private_inputs(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    process = subprocess.run(
        ["uv", "build", "--offline", "--out-dir", str(tmp_path)],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr
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
        for member in archive.getmembers():
            if not member.isfile():
                continue
            relative = member.name.split("/", 1)[1]
            assert relative.split("/")[0] in allowed or relative in {
                "docs/assumptions.md",
                "docs/domain-model.md",
            }, relative
    with zipfile.ZipFile(next(tmp_path.glob("*.whl"))) as wheel:
        for name in wheel.namelist():
            assert name.startswith("tkb_core/") or ".dist-info/" in name, name
