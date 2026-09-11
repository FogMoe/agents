"""Independently installed skills must carry the maintained runtime source."""

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "agent_runtime_sync", ROOT / "scripts/sync_agent_runtime.py"
)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


class RuntimeBundleTests(unittest.TestCase):
    def test_bundled_runtimes_match_canonical_source(self):
        self.assertEqual(
            sync.sync(ROOT, check=True), [], "Run python scripts/sync_agent_runtime.py"
        )


if __name__ == "__main__":
    unittest.main()
