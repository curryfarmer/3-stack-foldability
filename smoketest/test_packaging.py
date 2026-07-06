"""Packaging / import smoke tests for the fold3stack distribution.

Ground-truth-independent: works on a fresh clone with none of the gitignored local research
data (docs/, report/, results/) present. This is NOT a replacement for scripts/validate.py (the
real regression proof against physical ground truth) -- it only proves the package installs and
each CLI entry point runs, using `python -m <module> --help` / a tiny synthetic grid so it stays
fast and offline.

Each CLI is invoked in its own subprocess (never `import triangle...` and `import square...` in
the same interpreter -- both subpackages put a bare-named `lattice` module on sys.path via their
own _bootstrap.py, and importing both in one process is unsafe, see triangle/_bootstrap.py /
square/_bootstrap.py).
"""
import subprocess
import sys

CLI_MODULES = [
    "triangle.tri.render",
    "triangle.tri.generate",
    "square.render_cli",
    "square.generate",
]


def _run(*args):
    return subprocess.run([sys.executable, *args], capture_output=True, text=True)


def test_all_clis_help_exit_zero():
    for mod in CLI_MODULES:
        proc = _run("-m", mod, "--help")
        assert proc.returncode == 0, f"{mod} --help failed:\n{proc.stderr}"
        assert "usage" in proc.stdout.lower(), f"{mod} --help produced no usage text"


def test_triangle_generate_smoke(tmp_path):
    """Tiny known case (scalene 2+1 K=4) -> exactly one closing fold, full 4-image bundle."""
    proc = _run("-m", "triangle.tri.generate",
                "--tiling", "scalene", "--decomp", "2plus1", "--K", "4",
                "--out", str(tmp_path))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    bundles = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert len(bundles) == 1, f"expected 1 bundle, got {[p.name for p in bundles]}"
    uid_dir = bundles[0]
    uid = uid_dir.name
    for suffix in (f"{uid}.json", f"foldsheet_{uid}.png", f"overlay_{uid}.png", f"twist_{uid}.png"):
        assert (uid_dir / suffix).is_file(), f"missing {suffix} in {uid_dir}"


def test_triangle_render_roundtrip(tmp_path):
    """Re-rendering a generated record through tri-render reproduces the same file set."""
    gen_dir = tmp_path / "gen"
    proc = _run("-m", "triangle.tri.generate",
                "--tiling", "scalene", "--decomp", "2plus1", "--K", "4", "--out", str(gen_dir))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    uid_dir = next(p for p in gen_dir.iterdir() if p.is_dir())
    record = uid_dir / f"{uid_dir.name}.json"

    render_dir = tmp_path / "render"
    proc = _run("-m", "triangle.tri.render", str(record), "--out", str(render_dir))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    reproduced = render_dir / uid_dir.name
    assert reproduced.is_dir()
    assert {p.name for p in reproduced.iterdir()} == {p.name for p in uid_dir.iterdir()}


def test_square_generate_smoke(tmp_path):
    """Tiny known grid (6x4, 2+1 only) -> at least one bundle with the square output shape."""
    proc = _run("-m", "square.generate", "--m", "6", "--n", "4", "--decomps", "2+1",
                "--out", str(tmp_path))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    bundles = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert bundles, "expected at least one solution bundle for 6x4 2+1"
    uid_dir = bundles[0]
    uid = uid_dir.name
    assert (uid_dir / f"{uid}.json").is_file()
    assert (uid_dir / f"foldsheet_{uid}.png").is_file()


def test_square_render_roundtrip(tmp_path):
    gen_dir = tmp_path / "gen"
    proc = _run("-m", "square.generate", "--m", "6", "--n", "4", "--decomps", "2+1",
                "--out", str(gen_dir))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    uid_dir = next(p for p in gen_dir.iterdir() if p.is_dir())
    record = uid_dir / f"{uid_dir.name}.json"

    render_dir = tmp_path / "render"
    proc = _run("-m", "square.render_cli", str(record), "--out", str(render_dir))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    reproduced = render_dir / uid_dir.name
    assert reproduced.is_dir()
    assert {p.name for p in reproduced.iterdir()} == {p.name for p in uid_dir.iterdir()}
