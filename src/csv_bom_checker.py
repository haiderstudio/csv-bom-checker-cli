#!/usr/bin/env python3
"""Check CSV files for a byte-order mark (BOM) at the start.

Run: python3 src/csv_bom_checker.py data.csv
     python3 src/csv_bom_checker.py data/
     python3 src/csv_bom_checker.py --stdin < data.csv

A byte-order mark is the invisible bytes some editors
put at the very start of a file to say which encoding
it uses. In a CSV file it lands in front of the first
header, so most tools read the first column as
"BOM + id" instead of "id" — the import fails, or the
first column silently goes missing, and the file looks
fine in every editor. This tool reads the first bytes
of each CSV file, reports each file carrying a BOM,
with the file and the line (always line 1 — the BOM
sits at the very start), and exits 1 when any file
has one, so it can fail a CI run. A file with no BOM
exits 0.

"BOM" here means byte-order mark, not bill of
materials. The bill-of-materials tools that share
the name check electronics parts lists against
supplier data — a different job on the same
three letters, named honestly in the README.

It checks the UTF-8 BOM, the UTF-16 little- and
big-endian BOMs, and the UTF-32 little- and
big-endian BOMs. A BOM anywhere else in the file —
inside a value on a later line, for example — is not
flagged: only the bytes at the very start count.

It never rewrites a file, never touches the network,
and reads only the files and folders you point it at.
"""

import argparse
import fnmatch
import json
import os
import sys
from pathlib import Path

__version__ = "1.0.0"

# Byte-order marks, longest first so the UTF-32 marks
# are matched before the UTF-16 marks they start with.
BOM_MARKS = [
    (b"\xff\xfe\x00\x00", "UTF-32 LE"),
    (b"\x00\x00\xfe\xff", "UTF-32 BE"),
    (b"\xef\xbb\xbf", "UTF-8"),
    (b"\xff\xfe", "UTF-16 LE"),
    (b"\xfe\xff", "UTF-16 BE"),
]

CSV_SUFFIX = ".csv"


def check_bytes(data):
    """Return the BOM name at the start of bytes, or None.

    Only the very first bytes count — a BOM sequence
    anywhere later in the file is a value, not a mark.
    """
    for mark, name in BOM_MARKS:
        if data.startswith(mark):
            return name
    return None


def check_file(path):
    """Check one file. Returns (findings, error)."""
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        return [], str(exc)
    name = check_bytes(data)
    if name is None:
        return [], None
    return [{"line": 1, "bom": name}], None


def _is_csv_file(path):
    return Path(path).name.lower().endswith(CSV_SUFFIX)


def collect_files(paths, recursive=True, exclude=None):
    """Expand CLI paths into a sorted list of CSV files.

    A file given directly is always checked, whatever its
    name. A folder is walked for files ending in .csv
    only, recursively by default (--no-recursive stops
    at the top level). .git folders are never walked,
    and directory links are never followed.
    """
    exclude = exclude or []
    found = []
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            found.append(str(path))
        elif path.is_dir():
            for dirpath, dirs, files in os.walk(path, followlinks=False):
                dirs[:] = [
                    d for d in dirs
                    if d != ".git"
                    and not any(fnmatch.fnmatch(d, pat) for pat in exclude)
                ]
                for name in files:
                    candidate = Path(dirpath) / name
                    if not _is_csv_file(candidate):
                        continue
                    if any(
                        fnmatch.fnmatch(str(candidate), pat)
                        or fnmatch.fnmatch(name, pat)
                        for pat in exclude
                    ):
                        continue
                    found.append(str(candidate))
                if not recursive:
                    break
        else:
            raise FileNotFoundError("no such file or folder: %s" % raw)
    seen = set()
    unique = []
    for item in found:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return sorted(unique)


def format_finding(path, finding):
    """One human-readable line for one file with a BOM."""
    return ("FAIL %s: byte-order mark (BOM, %s) at line %d — "
            "save the file without a BOM so the first header "
            "reads cleanly" % (path, finding["bom"],
                               finding["line"]))


def run(paths, recursive=True, exclude=None, as_json=False):
    """Check paths, print the report, return the exit code."""
    try:
        files = collect_files(paths, recursive=recursive, exclude=exclude)
    except (FileNotFoundError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    if not files:
        print("error: no .csv files found", file=sys.stderr)
        return 2
    results = []
    findings = 0
    files_with_findings = 0
    for path in files:
        bad, error = check_file(path)
        count = len(bad) + (1 if error else 0)
        if count:
            findings += count
            files_with_findings += 1
        results.append({"path": path, "findings": bad, "error": error})
    if as_json:
        print(json.dumps(
            {"files": results, "checked": len(files),
             "findings": findings},
            indent=2))
    else:
        for result in results:
            if result["error"]:
                print("FAIL %s: %s" % (result["path"], result["error"]))
            for finding in result["findings"]:
                print(format_finding(result["path"], finding))
        if findings:
            print("Checked %d file(s), %d file(s) with a "
                  "byte-order mark." % (len(files),
                                        files_with_findings))
        else:
            print("OK — %d file(s) checked, no byte-order mark "
                  "found." % len(files))
    return 1 if findings else 0


def run_stdin(as_json=False):
    """Check one CSV document read from standard input."""
    data = sys.stdin.buffer.read()
    name = check_bytes(data)
    findings = [{"line": 1, "bom": name}] if name else []
    count = len(findings)
    if as_json:
        print(json.dumps(
            {"files": [{"path": "<stdin>", "findings": findings,
                        "error": None}],
             "checked": 1, "findings": count},
            indent=2))
    else:
        for finding in findings:
            print(format_finding("<stdin>", finding))
        if count:
            print("Checked 1 file(s), 1 file(s) with a "
                  "byte-order mark.")
        else:
            print("OK — 1 file(s) checked, no byte-order mark "
                  "found.")
    return 1 if count else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="csv_bom_checker",
        description="Check CSV files for a byte-order mark "
                    "(BOM) at the start, fail CI when one is "
                    "found. Report-only; it never edits a file.")
    parser.add_argument("paths", nargs="*",
                        help=".csv files or folders to walk")
    parser.add_argument("--no-recursive", action="store_true",
                        help="do not walk into subfolders")
    parser.add_argument("--exclude", action="append", default=[],
                        help="skip files or folders matching this pattern "
                             "(repeatable)")
    parser.add_argument("--json", action="store_true",
                        help="print the result as JSON")
    parser.add_argument("--stdin", action="store_true",
                        help="check one CSV document from standard input")
    parser.add_argument("--version", action="version",
                        version="%(prog)s " + __version__)
    args = parser.parse_args(argv)
    if args.stdin:
        if args.paths:
            parser.error("--stdin takes no file or folder arguments")
        return run_stdin(as_json=args.json)
    if not args.paths:
        parser.error("give at least one .csv file or folder")
    return run(args.paths, recursive=not args.no_recursive,
               exclude=args.exclude, as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
