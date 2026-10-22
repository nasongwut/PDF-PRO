"""Every Thai string wrapped in _() must have an English translation."""

import ast
import pathlib
import re

from pdfpro.locales.en import EN

THAI = re.compile("[฀-๿]")
ROOT = pathlib.Path(__file__).resolve().parents[1] / "pdfpro"


def _keys():
    for path in ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "_" and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and THAI.search(arg.value):
                    yield path.name, arg.value


def test_all_strings_translated():
    missing = sorted({(f, k) for f, k in _keys() if k not in EN})
    assert not missing, missing


def test_constant_tables_translated():
    from pdfpro.ui.constants import HINTS, TOOLS, TYPE_NAME

    texts = (
        [t for _k, label, _s, desc in TOOLS for t in (label, desc)] + list(HINTS.values()) + list(TYPE_NAME.values())
    )
    assert [t for t in texts if t not in EN] == []
