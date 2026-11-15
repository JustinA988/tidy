# tidy

Clean up messy folders like Downloads and Desktop. `tidy` finds duplicate files by their contents (even when they have different names, like `report.pdf` and `report (1).pdf`), sorts files into folders using simple rules, and can undo everything it did.

Single Python file, standard library only. Requires **Python 3.11+**.

## Usage

**1. Preview** (dry run, the default — nothing is moved):

```bash
python tidy.py ~/Downloads ~/Desktop --dest ~/Tidy --rules rules.toml
```

Each line of output is a planned move:

```
DUP  /home/you/Downloads/report (1).pdf -> /home/you/Tidy/_duplicates/report (1).pdf
MOVE /home/you/Downloads/CS101_Syllabus.pdf -> /home/you/Tidy/School/Syllabi/CS101_Syllabus.pdf
```

**2. Apply** when the plan looks right:

```bash
python tidy.py ~/Downloads ~/Desktop --dest ~/Tidy --rules rules.toml --apply
```

**3. Undo** with the manifest path printed by `--apply`:

```bash
python tidy.py --undo ~/Tidy/tidy-manifest-20261115-120000.json
```

## How it works

- **Fast duplicate detection.** Files are grouped by size first; only files that share an exact size are hashed with SHA-256. Files with a unique size are never read.
- **Nothing is deleted.** Duplicates are moved to `<dest>/_duplicates`. The oldest copy (by modified time) stays where it is.
- **Undo-safe.** A JSON manifest of every original and new path is written *before* any file moves, so even an interrupted run can be undone. Undo never overwrites a file that now occupies an original spot; it skips it and tells you.
- **Safe to re-run.** Already-sorted files and the `_duplicates` folder are left alone.

## Rules

Rules live in a TOML file. The first matching rule wins. `ext` and `contains` are optional; if both are given, both must match. `dest` is relative to `--dest`.

```toml
[[rule]]
ext = [".pdf"]
contains = ["invoice", "receipt"]
dest = "Finance/Invoices"
```

See [rules.toml](rules.toml) for more examples.

## Limitations

- `contains` matches the **filename**, not the text inside a file.
- Empty files are never treated as duplicates.
- Symlinks are skipped.

## Tests

```bash
python -m unittest -v
```
