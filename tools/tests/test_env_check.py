from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


TOOL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOL_ROOT))

from env_check import is_lfs_pointer


class EnvironmentCheckTests(unittest.TestCase):
    def test_detects_lfs_pointer(self) -> None:
        payload = io.BytesIO(
            b"version https://git-lfs.github.com/spec/v1\n"
            b"oid sha256:abc\nsize 123\n"
        )
        with patch("pathlib.Path.open", return_value=payload):
            self.assertTrue(is_lfs_pointer(Path("asset.bin")))

    def test_real_binary_is_not_pointer(self) -> None:
        payload = io.BytesIO(b"MPQ\x1a" + b"\0" * 32)
        with patch("pathlib.Path.open", return_value=payload):
            self.assertFalse(is_lfs_pointer(Path("asset.bin")))


if __name__ == "__main__":
    unittest.main()
