"""Evidence commands must reject existing outputs before expensive work."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReportOutputTests(unittest.TestCase):
    def test_existing_evidence_is_preserved_by_every_current_report_command(self):
        commands = (("analyze_maps.py", ()), ("check_player.py", ()),
                    ("check_search.py", ()), ("check_limits.py", ()),
                    ("check_tactics.py", ()), ("check_outcomes.py", ()),
                    ("analyze_league.py", ("nonexistent-run",)),
                    ("check_runtime.py", ("--reference", "HEAD")))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing.json"
            evidence = b'{"preserve": "original evidence"}\n'
            output.write_bytes(evidence)
            for script, options in commands:
                with self.subTest(script=script):
                    result = subprocess.run(
                        [sys.executable, str(ROOT / "tools" / script), *options,
                         "--output", str(output)], cwd=directory, capture_output=True,
                        text=True, timeout=5)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn("fresh output path", result.stderr)
                    self.assertEqual(output.read_bytes(), evidence)


if __name__ == "__main__":
    unittest.main()
