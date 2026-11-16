# Security Policy

This tool runs locally, collects no data, sends nothing anywhere, and needs no API key or secret. It only reads the CSV files you point it at, and it never rewrites a file and never changes anything. It writes nothing except the report on standard output (and usage errors on standard error). It never fetches a URL: remote addresses are skipped, not opened.

It only reads the first bytes of each file to check for a byte-order mark — it never parses or uploads the file's contents. A byte-order mark anywhere but the very start of a file is not flagged.

If you find a case where the tool edits a file, flags a file with no BOM at its start, or passes a file that starts with a BOM, please open an issue describing the exact commands and input.
