#!/usr/bin/env python3
"""Tests for csv_bom_checker — stdlib unittest only."""

import ast
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import csv_bom_checker as checker

REPO = Path(__file__).resolve().parent.parent

ROWS = b"id,name,price\n1,apple,0.50\n2,banana,0.30\n"
UTF8_BOM = b"\xef\xbb\xbf"
UTF16LE_BOM = b"\xff\xfe"
UTF16BE_BOM = b"\xfe\xff"
UTF32LE_BOM = b"\xff\xfe\x00\x00"
UTF32BE_BOM = b"\x00\x00\xfe\xff"


def run_cli(argv):
    """Run main(argv), capture stdout/stderr, return (code, out, err)."""
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = checker.main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def write(tmp, name, data):
    path = Path(tmp) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8")
    return str(path)


class TestCheckBytes(unittest.TestCase):
    def test_clean_bytes_pass(self):
        self.assertIsNone(checker.check_bytes(ROWS))

    def test_empty_file_passes(self):
        self.assertIsNone(checker.check_bytes(b""))

    def test_utf8_bom_flagged(self):
        self.assertEqual(checker.check_bytes(UTF8_BOM + ROWS), "UTF-8")

    def test_utf16le_bom_flagged(self):
        self.assertEqual(
            checker.check_bytes(UTF16LE_BOM + ROWS.decode().encode("utf-16-le")),
            "UTF-16 LE")

    def test_utf16be_bom_flagged(self):
        self.assertEqual(
            checker.check_bytes(UTF16BE_BOM + ROWS.decode().encode("utf-16-be")),
            "UTF-16 BE")

    def test_utf32le_bom_flagged(self):
        self.assertEqual(
            checker.check_bytes(UTF32LE_BOM + ROWS.decode().encode("utf-32-le")),
            "UTF-32 LE")

    def test_utf32be_bom_flagged(self):
        self.assertEqual(
            checker.check_bytes(UTF32BE_BOM + ROWS.decode().encode("utf-32-be")),
            "UTF-32 BE")

    def test_bom_only_file_flagged(self):
        self.assertEqual(checker.check_bytes(UTF8_BOM), "UTF-8")

    def test_bom_mid_file_passes(self):
        data = b"id,name\n1,\xef\xbb\xbfbanana\n"
        self.assertIsNone(checker.check_bytes(data))

    def test_bom_on_second_line_passes(self):
        data = b"id,name\n\xef\xbb\xbf1,apple\n"
        self.assertIsNone(checker.check_bytes(data))

    def test_almost_bom_passes(self):
        self.assertIsNone(checker.check_bytes(b"\xef\xbbid,name\n"))
        self.assertIsNone(checker.check_bytes(b"\xff\xfdid,name\n"))


class TestCheckFile(unittest.TestCase):
    def test_clean_file_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.csv", ROWS)
            findings, error = checker.check_file(path)
            self.assertEqual((findings, error), ([], None))

    def test_flagged_file_reports_line_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.csv", UTF8_BOM + ROWS)
            findings, error = checker.check_file(path)
            self.assertEqual(error, None)
            self.assertEqual(findings,
                             [{"line": 1, "bom": "UTF-8"}])

    def test_missing_file_reports_error(self):
        findings, error = checker.check_file(
            str(Path(tempfile.gettempdir()) / "no-such-csv-bom-file.csv"))
        self.assertEqual(findings, [])
        self.assertIsNotNone(error)

    def test_non_utf8_file_without_bom_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.csv", b"id;name\n1;\xff\xfe\n")
            findings, error = checker.check_file(path)
            self.assertEqual((findings, error), ([], None))


class TestCli(unittest.TestCase):
    def test_clean_file_exit_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.csv", ROWS)
            code, out, _err = run_cli([path])
            self.assertEqual(code, 0)
            self.assertIn("OK — 1 file(s) checked", out)

    def test_flagged_file_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.csv", UTF8_BOM + ROWS)
            code, out, _err = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("byte-order mark (BOM, UTF-8) at line 1", out)
            self.assertIn("Checked 1 file(s), 1 file(s) with a "
                          "byte-order mark.", out)

    def test_folder_walk(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "clean.csv", ROWS)
            write(tmp, "bad.csv", UTF8_BOM + ROWS)
            write(tmp, "notes.txt", UTF8_BOM + b"not a csv\n")
            code, out, _err = run_cli([tmp])
            self.assertEqual(code, 1)
            self.assertIn("bad.csv", out)
            self.assertNotIn("notes.txt", out)
            self.assertIn("Checked 2 file(s), 1 file(s) with a "
                          "byte-order mark.", out)

    def test_nested_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "sub/deep.csv", UTF8_BOM + ROWS)
            code, out, _err = run_cli([tmp])
            self.assertEqual(code, 1)
            self.assertIn("deep.csv", out)

    def test_no_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "top.csv", ROWS)
            write(tmp, "sub/deep.csv", UTF8_BOM + ROWS)
            code, out, _err = run_cli(["--no-recursive", tmp])
            self.assertEqual(code, 0)
            self.assertIn("OK — 1 file(s) checked", out)

    def test_exclude(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "bad.csv", UTF8_BOM + ROWS)
            write(tmp, "skip/bad.csv", UTF8_BOM + ROWS)
            code, out, _err = run_cli(["--exclude", "skip", tmp])
            self.assertEqual(code, 1)
            self.assertIn("Checked 1 file(s)", out)

    def test_git_folder_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, ".git/hooks/bad.csv", UTF8_BOM + ROWS)
            write(tmp, "good.csv", ROWS)
            code, out, _err = run_cli([tmp])
            self.assertEqual(code, 0)

    def test_direct_file_checked_whatever_its_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "data.txt", UTF8_BOM + ROWS)
            code, out, _err = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("data.txt", out)

    def test_duplicate_paths_checked_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.csv", UTF8_BOM + ROWS)
            code, out, _err = run_cli([path, path])
            self.assertEqual(code, 1)
            self.assertEqual(out.count("byte-order mark (BOM, UTF-8)"), 1)

    def test_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.csv", UTF8_BOM + ROWS)
            code, out, _err = run_cli(["--json", path])
            self.assertEqual(code, 1)
            data = json.loads(out)
            self.assertEqual(data["checked"], 1)
            self.assertEqual(data["findings"], 1)
            self.assertEqual(data["files"][0]["findings"],
                             [{"line": 1, "bom": "UTF-8"}])
            self.assertIsNone(data["files"][0]["error"])

    def test_stdin_flagged(self):
        out = io.StringIO()
        err = io.StringIO()
        old_stdin = sys.stdin
        try:
            sys.stdin = io.TextIOWrapper(
                io.BytesIO(UTF8_BOM + ROWS), encoding="utf-8")
            with redirect_stdout(out), redirect_stderr(err):
                code = checker.main(["--stdin"])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(code, 1)
        self.assertIn("byte-order mark (BOM, UTF-8) at line 1",
                      out.getvalue())

    def test_stdin_clean(self):
        out = io.StringIO()
        err = io.StringIO()
        old_stdin = sys.stdin
        try:
            sys.stdin = io.TextIOWrapper(
                io.BytesIO(ROWS), encoding="utf-8")
            with redirect_stdout(out), redirect_stderr(err):
                code = checker.main(["--stdin"])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(code, 0)
        self.assertIn("OK — 1 file(s) checked", out.getvalue())

    def test_stdin_with_path_is_usage_error(self):
        code, _out, err = run_cli(["--stdin", "a.csv"])
        self.assertEqual(code, 2)

    def test_bad_flag(self):
        code, _out, _err = run_cli(["--no-such-flag", "a.csv"])
        self.assertEqual(code, 2)

    def test_missing_path(self):
        code, _out, err = run_cli(["no-such-folder-xyz"])
        self.assertEqual(code, 2)
        self.assertIn("no such file or folder", err)

    def test_empty_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _out, err = run_cli([tmp])
            self.assertEqual(code, 2)
            self.assertIn("no .csv files found", err)

    def test_no_paths(self):
        code, _out, _err = run_cli([])
        self.assertEqual(code, 2)

    def test_version(self):
        code, out, _err = run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("csv_bom_checker 1.0.0", out)

    def test_unreadable_file_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.csv", ROWS)
            os.chmod(path, 0)
            try:
                code, out, _err = run_cli([path])
                if os.geteuid() == 0:
                    self.assertEqual(code, 0)
                else:
                    self.assertEqual(code, 1)
                    self.assertIn("FAIL", out)
            finally:
                os.chmod(path, 0o644)

    def test_input_files_left_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.csv", UTF8_BOM + ROWS)
            run_cli([path])
            self.assertEqual(Path(path).read_bytes(), UTF8_BOM + ROWS)

    def test_tool_runs_from_a_temp_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.csv", UTF8_BOM + ROWS)
            result = subprocess.run(
                [sys.executable,
                 str(REPO / "src/csv_bom_checker.py"), "a.csv"],
                cwd=tmp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("byte-order mark (BOM, UTF-8) at line 1",
                          result.stdout)

    def test_tool_runs_from_root(self):
        result = subprocess.run(
            [sys.executable,
             str(REPO / "src/csv_bom_checker.py"),
             str(REPO / "examples/clean.csv")],
            cwd="/", capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)


class TestExamples(unittest.TestCase):
    def test_run_example_output_matches_sample(self):
        result = subprocess.run(
            ["sh", "examples/run-example.sh"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        expected = (REPO / "examples/sample-output.md").read_text()
        self.assertEqual(result.stdout, expected)

    def test_readme_quotes_match_real_runs(self):
        readme = (REPO / "README.md").read_text()
        clean = subprocess.run(
            [sys.executable, "src/csv_bom_checker.py",
             "examples/clean.csv"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(clean.returncode, 0)
        self.assertIn(clean.stdout.strip(), readme)
        flagged = subprocess.run(
            [sys.executable, "src/csv_bom_checker.py",
             "examples/flagged.csv"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(flagged.returncode, 1)
        self.assertIn(flagged.stdout.strip(), readme)
        folder = subprocess.run(
            [sys.executable, "src/csv_bom_checker.py",
             "examples/"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(folder.returncode, 1)
        self.assertIn("Checked 4 file(s), 2 file(s) with a "
                      "byte-order mark.", folder.stdout)
        self.assertIn("Checked 4 file(s), 2 file(s) with a "
                      "byte-order mark.", readme)
        edge = subprocess.run(
            [sys.executable, "src/csv_bom_checker.py",
             "examples/edge.csv"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(edge.returncode, 0)
        self.assertIn(edge.stdout.strip(), readme)
        utf16 = subprocess.run(
            [sys.executable, "src/csv_bom_checker.py",
             "examples/utf16.csv"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(utf16.returncode, 1)
        self.assertIn(utf16.stdout.strip(), readme)
        js = subprocess.run(
            [sys.executable, "src/csv_bom_checker.py",
             "--json", "examples/flagged.csv"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(js.returncode, 1)
        self.assertIn(js.stdout.strip(), readme)
        stdin = subprocess.run(
            [sys.executable, "src/csv_bom_checker.py", "--stdin"],
            input=ROWS, cwd=REPO, capture_output=True)
        self.assertEqual(stdin.returncode, 0)
        self.assertIn(stdin.stdout.decode().strip(), readme)


class TestHygiene(unittest.TestCase):
    def _repo_files(self, skip_tests=True, skip_examples=True):
        for root, dirs, files in os.walk(REPO):
            dirs[:] = [d for d in dirs
                       if d not in (".git", "__pycache__")
                       and not (skip_tests and d == "tests")
                       and not (skip_examples and d == "examples")]
            for name in files:
                if name.endswith(".pyc"):
                    continue
                yield Path(root) / name

    def test_no_placeholder_text(self):
        banned = ["TODO", "coming soon", "lorem", "FIXME", "XXX"]
        hits = []
        for path in self._repo_files(skip_tests=True,
                                     skip_examples=False):
            text = path.read_text(errors="ignore")
            for word in banned:
                if word in text:
                    hits.append("%s: %s" % (path.name, word))
        self.assertEqual(hits, [])

    def test_no_absolute_paths(self):
        hits = []
        for path in self._repo_files(skip_tests=True,
                                     skip_examples=False):
            text = path.read_text(errors="ignore")
            for marker in ("/home/", "/Users/", "C:\\", "/tmp/"):
                if marker in text:
                    hits.append("%s: %s" % (path.name, marker))
        self.assertEqual(hits, [])

    def test_no_bom_in_shipped_text_files(self):
        # The flagged example CSVs carry a BOM on purpose;
        # they are fixtures, not shipped text. Everything
        # else must be BOM-free.
        for path in self._repo_files(skip_tests=True,
                                     skip_examples=True):
            data = path.read_bytes()
            self.assertFalse(
                data.startswith(b"\xef\xbb\xbf"),
                "%s starts with a BOM" % path.name)

    def test_stdlib_imports_only(self):
        stdlib = set(sys.stdlib_module_names)
        for target in (REPO / "src/csv_bom_checker.py",
                       REPO / "tests/test_csv_bom_checker.py"):
            tree = ast.parse(target.read_text())
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(a.name.split(".")[0]
                                    for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            self.assertFalse(
                imported - stdlib - {"csv_bom_checker"},
                (target.name, imported))
            self.assertNotIn("yaml", imported)

    def test_no_network_use_in_src(self):
        src = (REPO / "src/csv_bom_checker.py").read_text()
        for marker in ("urllib.request", "requests", "socket",
                       "http.client", "urlopen", "urlretrieve"):
            self.assertNotIn(marker, src, marker)

    def test_gitignore_lists_env_first(self):
        lines = (REPO / ".gitignore").read_text().splitlines()
        self.assertEqual(lines[0], ".env")

    def test_ci_runs_this_test_file(self):
        ci = (REPO / ".github/workflows/ci.yml").read_text()
        self.assertIn("tests/test_csv_bom_checker.py", ci)
        self.assertIn("ubuntu-latest", ci)
        self.assertIn("3.12", ci)
        self.assertIn("actions/checkout", ci)
        self.assertIn("setup-python", ci)
        self.assertIn("push", ci)
        self.assertIn("pull_request", ci)

    def test_readme_names_the_neighbouring_repos(self):
        readme = (REPO / "README.md").read_text()
        self.assertIn("csv-column-count-checker-cli", readme)
        self.assertIn("csv-empty-checker-cli", readme)
        self.assertIn("csv-quote-checker-cli", readme)
        self.assertIn('"BOM" means byte-order mark here', readme)
        self.assertIn("not bill of", readme)
        self.assertIn("materials", readme)


if __name__ == "__main__":
    unittest.main()
