"""Build or check the combined distribution copy of the split team spec."""
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    parts = sorted((ROOT / "Mark1-Team-Spec").glob("[0-9][0-9]-*.md"))
    text = "# Mark-1: complete team implementation specification\n\n"
    text += "Version 2.0 | 10 November 2026 | Visual investigation baseline.\n\n"
    text += "Generated from the split specifications; edit those files first. "
    text += "Companion contracts and backlog are in `Mark1-Team-Spec/`.\n\n"
    for part in parts:
        text += f"---\n\n<!-- {part.name} -->\n\n{part.read_text(encoding='utf-8').rstrip()}\n\n"
    text = text.rstrip() + "\n"
    output = ROOT / "Mark1-Team-Implementation-Spec.md"
    if args.check:
        if output.read_text(encoding="utf-8") != text:
            raise SystemExit("Combined specification is stale; run this script without --check.")
        print(f"Combined specification matches {len(parts)} split documents.")
    else:
        output.write_text(text, encoding="utf-8")
        print(f"Built combined specification from {len(parts)} split documents.")


if __name__ == "__main__":
    main()
