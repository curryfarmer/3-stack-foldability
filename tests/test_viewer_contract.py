"""test_viewer_contract.py — bind the browser viewer's accepted JSON shape to py/store.py output.

The viewer loads results via `loadResultsData(data)` (app.js:486-503). Its only hard requirement is:
a top-level JSON **array**, OR an **object whose `solutions` is an array**; `meta` is optional and, when
present, an object. `_accepts()` below mirrors that guard exactly.

py/store.py writes `{meta:{m,n,stacks,opts,generated,counts}, solutions:[...]}` (store.py:71-75). This
test proves (a) every committed result file the viewer would fetch satisfies the loader contract AND
carries the full store meta keys, and (b) the loader contract actually *rejects* malformed shapes — so
the positive assertions aren't vacuous. If store.py's payload keys change, this fails.
"""
from __future__ import annotations

import json
import os
from typing import Any

import pytest

_HERE: str = os.path.dirname(os.path.abspath(__file__))
_RESULTS: str = os.path.join(os.path.dirname(_HERE), "results")

# Full meta contract emitted by store.save_result (store.py:71-75).
_META_KEYS = {"m", "n", "stacks", "opts", "generated", "counts"}


def _accepts(data: Any) -> bool:
    """Mirror of loadResultsData's guard (app.js:486-503): a bare list, or an object with a
    `solutions` list (and `meta`, if present, an object). I/O: (parsed JSON) -> bool."""
    if isinstance(data, list):
        return True
    if not isinstance(data, dict):
        return False
    if not isinstance(data.get("solutions"), list):
        return False
    if "meta" in data and not isinstance(data["meta"], dict):
        return False
    return True


def _live_result_files() -> list[str]:
    """Committed result files referenced by the manifest that still exist on disk.
    I/O: () -> list[str] (basenames). Mirrors test_manifest_counts._live_entries."""
    path = os.path.join(_RESULTS, "manifest.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        entries = json.load(f)
    return [e["file"] for e in entries if os.path.exists(os.path.join(_RESULTS, e["file"]))]


def _params() -> list[Any]:
    files = _live_result_files()
    return [pytest.param(f, id=f) for f in files] or [pytest.param(None, id="no-results")]


@pytest.mark.parametrize("fname", _params())
def test_live_result_file_matches_viewer_contract(fname: str | None) -> None:
    """Every committed result file loads under the viewer contract and carries store.py's meta keys.
    I/O: (result filename | None) -> None (asserts shape)."""
    if fname is None:
        pytest.skip("no committed result files on disk")
    with open(os.path.join(_RESULTS, fname)) as f:
        data = json.load(f)
    assert _accepts(data), f"{fname}: viewer would reject this shape"
    assert isinstance(data, dict), f"{fname}: store output is an object, not a bare array"
    assert isinstance(data["solutions"], list)
    meta = data.get("meta")
    assert isinstance(meta, dict), f"{fname}: missing meta object"
    assert _META_KEYS <= set(meta), f"{fname}: meta missing {_META_KEYS - set(meta)}"
    assert isinstance(meta["opts"], dict)


@pytest.mark.parametrize("good", [
    [],                                   # bare empty array
    [{"id": 1}],                          # bare non-empty array
    {"solutions": []},                    # object, empty solutions
    {"meta": {"m": 6, "n": 4}, "solutions": [{"id": 1}]},  # full-ish object
])
def test_accepts_good_shapes(good: Any) -> None:
    """Loader contract accepts arrays and {solutions:[...]} objects. I/O: (data) -> None."""
    assert _accepts(good)


@pytest.mark.parametrize("bad", [
    {},                          # no solutions key
    {"meta": {}},                # meta but no solutions
    {"solutions": "x"},          # solutions not a list
    {"solutions": {}},           # solutions not a list
    {"solutions": [], "meta": 1},  # meta present but not an object
    42,                          # scalar
    "solutions",                 # string
    None,                        # null
])
def test_rejects_bad_shapes(bad: Any) -> None:
    """Loader contract rejects malformed shapes (proves the positive checks aren't vacuous).
    I/O: (data) -> None."""
    assert not _accepts(bad)
