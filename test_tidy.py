import tempfile
import unittest
from pathlib import Path

import tidy


class TidyTest(unittest.TestCase):
    def test_dupes_rules_and_undo(self):
        with tempfile.TemporaryDirectory() as t:
            root, dest = Path(t, "Downloads"), Path(t, "Tidy")
            root.mkdir()
            files = {
                "report.pdf": b"same bytes",
                "report (1).pdf": b"same bytes",   # duplicate, different name
                "other.txt": b"diff bytes",        # same size, different content
                "CS101_Syllabus.pdf": b"syllabus!",
                "empty1.txt": b"",
                "empty2.txt": b"",
            }
            for name, data in files.items():
                (root / name).write_bytes(data)
            rules = tidy.load_rules(Path(__file__).with_name("rules.toml"))

            moves = tidy.plan([root.resolve()], dest.resolve(), rules)
            kinds = {(k, s.name) for k, s, _ in moves}
            self.assertEqual(kinds, {("DUP", "report (1).pdf"), ("MOVE", "CS101_Syllabus.pdf")})

            manifest = dest / "tidy-manifest-test.json"
            tidy.apply(moves, manifest)
            self.assertTrue((dest / "_duplicates" / "report (1).pdf").exists())
            self.assertTrue((dest / "School/Syllabi/CS101_Syllabus.pdf").exists())
            self.assertEqual(tidy.plan([root.resolve(), dest.resolve()], dest.resolve(), rules), [])  # idempotent

            tidy.undo(manifest)
            for name, data in files.items():
                self.assertEqual((root / name).read_bytes(), data)


if __name__ == "__main__":
    unittest.main()
