#!/usr/bin/env python3
"""Apply the TempRoot patches to a Magisk source checkout.

Usage:
    python3 patches/apply_temp_root.py <magisk-source-dir> [--check]

Design notes
------------
The manager UI is Jetpack Compose (no XML layouts), so the two actions are
hidden by rewriting the Kotlin source. Upstream moves code around between
releases, so this script never "best-effort" edits: every rule in
``patches/targets.json`` must match exactly once, otherwise it prints the
candidate lines and exits non-zero (the CI job then fails, so no half-patched
APK is ever published).

Each rule:
    file      path relative to the Magisk checkout
    find      regular expression (Python, MULTILINE)
    replace   replacement text (may use \\1 backreferences)
    required  true  -> must match exactly once
    why       human readable reason (printed on failure)
"""

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_rules():
    with open(HERE / "targets.json", encoding="utf-8") as fh:
        return json.load(fh)["rules"]


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    root = Path(argv[1])
    check_only = "--check" in argv
    if not root.is_dir():
        print(f"error: {root} is not a directory")
        return 2

    failures = []
    for rule in load_rules():
        path = root / rule["file"]
        if not path.is_file():
            failures.append(
                f"{rule['file']}: file not found "
                f"(ref predates v31.0 / uses HomeFragment.kt, or upstream moved it)"
            )
            continue
        text = path.read_text(encoding="utf-8")
        matches = list(re.finditer(rule["find"], text, re.MULTILINE))
        if len(matches) != 1:
            failures.append(
                f"{rule['file']}: expected 1 match for /{rule['find'][:60]}.../ "
                f"({rule['why']}), found {len(matches)}"
            )
            for m in matches[:5]:
                line = text[: m.start()].count("\n") + 1
                print(f"  candidate line {line}: {m.group(0).splitlines()[0][:100]}")
            continue
        if check_only:
            print(f"ok   {rule['file']}: {rule['why']}")
            continue
        new = re.sub(rule["find"], rule["replace"], text, count=1, flags=re.MULTILINE)
        # Preserve the file's line endings: writing with the default newline on
        # Windows would rewrite the whole file as CRLF (huge, pointless diff).
        eol = "\r\n" if "\r\n" in text else "\n"
        with open(path, "w", encoding="utf-8", newline=eol) as fh:
            fh.write(new)
        print(f"patched {rule['file']}: {rule['why']}")

    if failures:
        print("\nFAILED - upstream layout changed, update patches/targets.json:")
        for f in failures:
            print("  -", f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
