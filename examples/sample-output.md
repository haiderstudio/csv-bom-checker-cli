== examples/clean.csv ==
OK — 1 file(s) checked, no byte-order mark found.

== examples/flagged.csv ==
FAIL examples/flagged.csv: byte-order mark (BOM, UTF-8) at line 1 — save the file without a BOM so the first header reads cleanly
Checked 1 file(s), 1 file(s) with a byte-order mark.

== examples/edge.csv ==
OK — 1 file(s) checked, no byte-order mark found.

== examples/utf16.csv ==
FAIL examples/utf16.csv: byte-order mark (BOM, UTF-16 LE) at line 1 — save the file without a BOM so the first header reads cleanly
Checked 1 file(s), 1 file(s) with a byte-order mark.

== examples/ : the whole folder ==
FAIL examples/flagged.csv: byte-order mark (BOM, UTF-8) at line 1 — save the file without a BOM so the first header reads cleanly
FAIL examples/utf16.csv: byte-order mark (BOM, UTF-16 LE) at line 1 — save the file without a BOM so the first header reads cleanly
Checked 4 file(s), 2 file(s) with a byte-order mark.
