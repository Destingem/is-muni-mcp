"""Testy packaging entry-pointů (kompilace + detekce piped stdin)."""

import os
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PACKAGING = ROOT / "packaging"

sys.path.insert(0, str(PACKAGING))
import entry_setup  # noqa: E402


def test_entry_pointy_se_zkompiluji():
    for name in ("entry_server.py", "entry_setup.py", "build_bin.py"):
        py_compile.compile(str(PACKAGING / name), doraise=True)


def test_stdin_pipe_detekce():
    r, w = os.pipe()
    try:
        with os.fdopen(r) as f:
            old = sys.stdin
            sys.stdin = f
            try:
                assert entry_setup._stdin_is_pipe() is True
            finally:
                sys.stdin = old
    finally:
        os.close(w)


def test_stdin_devnull_neni_pipe():
    with open(os.devnull) as f:
        old = sys.stdin
        sys.stdin = f
        try:
            assert entry_setup._stdin_is_pipe() is False
        finally:
            sys.stdin = old
