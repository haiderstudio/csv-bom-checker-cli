# csv-bom-checker-cli

Check CSV files for a byte-order mark (BOM) at the start, fail CI when one is found — it never edits a file.

[![CI](https://github.com/haiderstudio/csv-bom-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/csv-bom-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`csv_bom_checker` reads the first bytes of each CSV
file, reports each file carrying a byte-order mark,
with the file and the line (always line 1 — the BOM
sits at the very start), and exits 1 when any file
has one, so it can fail a CI run. A file with no BOM
exits 0.

- A byte-order mark is the invisible bytes some
  editors put at the very start of a file to say
  which encoding it uses. In a CSV file it lands in
  front of the first header, so most tools read the
  first column as "BOM + id" instead of "id" — the
  import fails, or the first column silently goes
  missing, and the file looks fine in every editor.
  This catches it before the file ships.
- **"BOM" means byte-order mark here, not bill of
  materials.** The bill-of-materials tools that
  share the name check electronics parts lists
  against supplier data — a different job on the
  same three letters, named honestly in the "How
  this differs" section below.
- It checks five marks: UTF-8, UTF-16 little- and
  big-endian, and UTF-32 little- and big-endian.
  The report names which one it found, so you know
  what the file was saved as.
- A BOM anywhere else in the file — inside a value
  on a later line, for example — is not flagged:
  only the bytes at the very start count.
- A file given directly on the command line is
  always checked, whatever its name. A folder is
  walked for files ending in `.csv` only,
  recursively by default (`--no-recursive` stops
  at the top level). `.git` folders are never
  walked, and directory links are never followed.
- `--json` prints the result as JSON, and `--stdin`
  checks one CSV document read from standard
  input.
- A file that cannot be read is reported as an
  error and fails the run, instead of being
  silently skipped.

## Who it is for

Anyone who ships CSV data files — data exports,
seed files, test fixtures, spreadsheets saved as
CSV. One stray BOM renames the first header in
most tools, and the file looks fine in every
editor, so the failure shows up far away from the
cause: a broken import, a missing first column, a
pipeline that quietly drops data. This is the gate
that names the file before it ships.

## What it does NOT do

- It never edits a file. Removing a BOM is a
  one-byte save in your editor — this tool only
  reports it.
- It does not check the shape of the rows, the
  header names, or whether the file is empty. That
  is repo #58, csv-column-count-checker-cli, repo
  #73, csv-empty-checker-cli, and repo #80,
  csv-quote-checker-cli — row shape, emptiness,
  and quotes are different checks on the same
  files.
- It does not check the file's encoding beyond
  the BOM. A file saved as UTF-16 without a BOM
  still reads as garbage in most tools, and this
  gate does not catch that — it catches the mark
  itself.
- It does not fix a BOM in the middle of a file.
  A BOM character inside a value on a later line
  is data, not a mark, and it is left alone.
- It never touches the network.

## How this differs

- A fresh search of GitHub on Nov 14, 2026 found
  0 results for `"csv-bom-checker-cli"` and 4
  results for `csv bom checker` — all four are
  bill-of-materials tools, a different "BOM":
  - zenoutlabs/salam-bomcheck, 0 stars — an
    offline electronics parts-list checker that
    finds duplicate references and quantity
    mismatches in a bill of materials.
  - Aightech/lcsc_bom_checker, 0 stars —
    validates a CSV bill of materials against
    supplier data from LCSC/JLCPCB.
  - Nothing0g/plm-pp-bom-readiness-checker,
    0 stars — CSV readiness checks for a
    product-structure handoff between PLM and
    production planning.
  - dpineer/BOM_checker, 0 stars — a tool for
    managing a component inventory, using CSV
    files to hold the inventory list.
- None of them checks a byte-order mark in a CSV
  file. So the narrow slice stands: the bytes at
  the very start of the file only, per-file
  reporting with the BOM type named, a CI exit
  code, and no edits.

## Install

```sh
git clone https://github.com/haiderstudio/csv-bom-checker-cli.git
cd csv-bom-checker-cli
```

There is nothing else to install: Python 3.10 or newer,
standard library only, no dependencies.

## Usage

Check one CSV file:

```sh
python3 src/csv_bom_checker.py data.csv
```

A file with no BOM passes:

```sh
$ python3 src/csv_bom_checker.py examples/clean.csv
OK — 1 file(s) checked, no byte-order mark found.
```

A file with a UTF-8 BOM fails, with the file and
the line — always line 1:

```sh
$ python3 src/csv_bom_checker.py examples/flagged.csv
FAIL examples/flagged.csv: byte-order mark (BOM, UTF-8) at line 1 — save the file without a BOM so the first header reads cleanly
Checked 1 file(s), 1 file(s) with a byte-order mark.
```

Check a whole folder (`.csv` files only):

```sh
$ python3 src/csv_bom_checker.py examples/
FAIL examples/flagged.csv: byte-order mark (BOM, UTF-8) at line 1 — save the file without a BOM so the first header reads cleanly
FAIL examples/utf16.csv: byte-order mark (BOM, UTF-16 LE) at line 1 — save the file without a BOM so the first header reads cleanly
Checked 4 file(s), 2 file(s) with a byte-order mark.
```

Check one document from standard input:

```sh
$ python3 src/csv_bom_checker.py --stdin < examples/flagged.csv
FAIL <stdin>: byte-order mark (BOM, UTF-8) at line 1 — save the file without a BOM so the first header reads cleanly
Checked 1 file(s), 1 file(s) with a byte-order mark.
```

```sh
$ python3 src/csv_bom_checker.py --stdin < examples/clean.csv
OK — 1 file(s) checked, no byte-order mark found.
```

Machine-readable output:

```sh
$ python3 src/csv_bom_checker.py --json examples/flagged.csv
{
  "files": [
    {
      "path": "examples/flagged.csv",
      "findings": [
        {
          "line": 1,
          "bom": "UTF-8"
        }
      ],
      "error": null
    }
  ],
  "checked": 1,
  "findings": 1
}
```

Exit codes: 0 when no file carries a BOM, 1 when
any file carries a BOM or a file cannot be read, 2
for a usage error (a missing path, a bad flag, or no
`.csv` files found).

## Examples

A BOM in the middle of a file is data, not a mark
— `examples/edge.csv` has a BOM character inside a
value on line 2, plus a quoted field holding a
comma and CRLF endings, and it passes:

```sh
$ python3 src/csv_bom_checker.py examples/edge.csv
OK — 1 file(s) checked, no byte-order mark found.
```

A UTF-16 file with its own BOM is flagged too, and
the report names the mark:

```sh
$ python3 src/csv_bom_checker.py examples/utf16.csv
FAIL examples/utf16.csv: byte-order mark (BOM, UTF-16 LE) at line 1 — save the file without a BOM so the first header reads cleanly
Checked 1 file(s), 1 file(s) with a byte-order mark.
```

Run every bundled example at once with `sh
examples/run-example.sh` — the output is saved in
[examples/sample-output.md](examples/sample-output.md).

## How it is tested

```sh
python3 tests/test_csv_bom_checker.py
```

The tests cover BOM detection (UTF-8, UTF-16
little- and big-endian, UTF-32 little- and
big-endian, a BOM-only file, a BOM in the middle
of a file, a BOM on the second line, near-miss
byte pairs, empty files, non-UTF-8 files without a
BOM, a missing file reported as an error), the CLI
(exit 0/1/2, folder walking, nested folders,
`--no-recursive`, `--exclude`, `.git` skipped, a
direct file checked whatever its name, duplicate
paths checked once, `--json` output, `--stdin`
flagged and clean, `--stdin` with a path refused,
bad flags, missing paths, empty folders, no paths,
`--version`, input files left unchanged, the tool
run from a temp folder and from `/`), the bundled
examples (sample output compared byte-for-byte
against a fresh run, and the README-quoted outputs
checked against it), and hygiene checks (no
placeholder text, no absolute paths, no BOM in any
shipped text file, stdlib imports only, no network
use in the source, `.env` first in `.gitignore`,
CI file runs the test file, README names the
neighbouring repos).

## Contributing

Small, focused improvements are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool was written from scratch for this repo.
The idea of a byte-order mark is not new, and the
five marks it checks are the standard ones every
encoding reference lists — but no existing tool
checks a CSV file for a BOM at the start as a
tested command-line gate, as the search above
shows — and every line of code here is original,
built on nothing but Python's standard library.
