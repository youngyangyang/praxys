"""Fill missing translations in Lingui .po catalogs (and science YAML files) via the Claude API.

Minimal-maintenance translation pipeline: English source text is authored in
the source code (extracted by `lingui extract` into `src/locales/en/messages.po`),
this script diff-reads the target-language catalog and fills any entries with
an empty `msgstr` using Claude. The output is a PR-ready `.po` that a human
reviews before merging.

Usage:
    # Fill missing zh translations in the .po catalog
    python scripts/translate_missing.py po \
        --source web/src/locales/en/messages.po \
        --target web/src/locales/zh/messages.po \
        --language "Simplified Chinese"

    # Translate every science YAML that lacks a zh counterpart
    python scripts/translate_missing.py yaml \
        --source-dir data/science \
        --target-dir data/science/zh \
        --language "Simplified Chinese"

Environment:
    ANTHROPIC_API_KEY must be set. Defaults to model claude-opus-4-7 (1M context).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    import anthropic  # type: ignore[import-not-found]
except ImportError:
    anthropic = None  # handled in main()

MODEL = os.environ.get("TRANSLATE_MODEL", "claude-opus-4-7")


# ---------------------------------------------------------------------------
# .po file parsing (minimal — enough for Lingui's format)
# ---------------------------------------------------------------------------

def parse_po(path: Path) -> list[dict]:
    """Parse a .po file into a list of {msgid, msgstr, prefix_lines} dicts.

    `prefix_lines` captures comments (#: ...) preceding each entry so we can
    write the file back identically aside from the translated `msgstr`.
    """
    entries: list[dict] = []
    header_written = False
    buf: list[str] = []
    msgid: str | None = None
    msgstr: str | None = None

    def _flush():
        nonlocal msgid, msgstr, buf
        if msgid is None:
            return
        entries.append({
            "prefix_lines": list(buf),
            "msgid": msgid,
            "msgstr": msgstr or "",
        })
        buf = []
        msgid = None
        msgstr = None

    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        raw = lines[i].rstrip("\n")
        stripped = raw.strip()
        if stripped.startswith("msgid "):
            _flush()
            msgid = _read_po_string(lines, i, "msgid ")
            i = _skip_continuation(lines, i)
            # Next non-blank should be msgstr
            while i < len(lines) and not lines[i].startswith("msgstr "):
                i += 1
            if i < len(lines):
                msgstr = _read_po_string(lines, i, "msgstr ")
                i = _skip_continuation(lines, i)
            continue
        if not header_written and (stripped.startswith("#") or stripped == ""):
            buf.append(raw)
        else:
            buf.append(raw)
        i += 1

    _flush()
    return entries


def _read_po_string(lines: list[str], idx: int, prefix: str) -> str:
    """Read a multiline quoted string from .po starting at prefix, following continuation lines."""
    assert lines[idx].lstrip().startswith(prefix)
    rest = lines[idx].lstrip()[len(prefix):].strip()
    parts = [_unquote(rest)]
    j = idx + 1
    while j < len(lines):
        nxt = lines[j].strip()
        if nxt.startswith('"') and nxt.endswith('"'):
            parts.append(_unquote(nxt))
            j += 1
            continue
        break
    return "".join(parts)


def _skip_continuation(lines: list[str], idx: int) -> int:
    """Return the index after a msgid/msgstr and its continuation lines."""
    j = idx + 1
    while j < len(lines):
        nxt = lines[j].strip()
        if nxt.startswith('"') and nxt.endswith('"'):
            j += 1
            continue
        return j
    return j


def _unquote(s: str) -> str:
    if s.startswith('"') and s.endswith('"'):
        return bytes(s[1:-1], "utf-8").decode("unicode_escape")
    return s


def _quote(s: str) -> str:
    escaped = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def write_po(path: Path, entries: list[dict]) -> None:
    """Write entries back in .po format."""
    out: list[str] = []
    for e in entries:
        out.extend(e["prefix_lines"])
        out.append(f"msgid {_quote(e['msgid'])}")
        out.append(f"msgstr {_quote(e['msgstr'])}")
        if not out[-1].endswith("\n"):
            pass
        out.append("")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Translation via Claude
# ---------------------------------------------------------------------------

def _client():
    if anthropic is None:
        print("anthropic SDK not installed. Run: pip install anthropic", file=sys.stderr)
        sys.exit(2)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY is not set — nothing to translate.", file=sys.stderr)
        sys.exit(2)
    return anthropic.Anthropic(api_key=api_key)


SYSTEM_PROMPT = """You translate UI strings for Trainsight, a power-based training dashboard for
endurance athletes. Keep technical terms (CP, FTP, HRV, TSB, RSS, km, W, bpm,
/km, /mi) unchanged. Preserve ICU/MessageFormat placeholders like {name},
{count, plural, one {#} other {#}}, and <0>...</0> XML tags verbatim. Match
the punctuation style of the source (ellipses, quote marks). Output the
translation only, with no prefix, quotes, or explanation."""


def translate_batch(entries: list[dict], language: str, batch_size: int = 20) -> None:
    """Translate entries whose msgstr is empty; mutates entries in place."""
    missing = [e for e in entries if not e["msgstr"]]
    if not missing:
        print("No missing translations.", file=sys.stderr)
        return
    client = _client()
    print(f"Translating {len(missing)} entries to {language}...", file=sys.stderr)
    for start in range(0, len(missing), batch_size):
        chunk = missing[start:start + batch_size]
        numbered = "\n".join(f"{i + 1}. {e['msgid']}" for i, e in enumerate(chunk))
        resp = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": (
                    f"Translate these UI strings to {language}. "
                    f"Output each on its own line in the same order, numbered 1., 2., 3., etc. "
                    f"No extra commentary:\n\n{numbered}"
                ),
            }],
        )
        text = resp.content[0].text  # type: ignore[attr-defined]
        lines = [ln for ln in text.strip().splitlines() if ln.strip()]
        for i, entry in enumerate(chunk):
            line = lines[i] if i < len(lines) else ""
            # Strip leading "N. " numbering
            if line[:4].strip().rstrip(".").isdigit():
                line = line.split(".", 1)[1].strip() if "." in line else line
            entry["msgstr"] = line


# ---------------------------------------------------------------------------
# YAML file walking
# ---------------------------------------------------------------------------

def translate_yaml_tree(source_dir: Path, target_dir: Path, language: str) -> None:
    """For each `data/science/*/theory.yaml`, if no counterpart exists under
    `target_dir/<pillar>/theory.yaml`, translate the text fields with Claude
    and write the result.
    """
    import yaml

    client = _client()
    source_dir = source_dir.resolve()
    target_dir = target_dir.resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    translatable_keys = {"name", "description", "simple_description", "advanced_description"}

    created = 0
    for src_path in source_dir.rglob("*.yaml"):
        # Skip files already under target_dir
        try:
            src_path.relative_to(target_dir)
            continue
        except ValueError:
            pass
        rel = src_path.relative_to(source_dir)
        dst_path = target_dir / rel
        if dst_path.exists():
            continue

        with open(src_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        to_translate = {k: v for k, v in (data or {}).items()
                        if k in translatable_keys and isinstance(v, str) and v.strip()}
        if not to_translate:
            continue

        numbered = "\n\n".join(f"[{k}]\n{v}" for k, v in to_translate.items())
        resp = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": (
                    f"Translate the following Trainsight science YAML fields to {language}. "
                    f"Preserve markdown formatting (headings, tables, lists, code). Keep "
                    f"technical terms in English where standard. Output each field as "
                    f"`[key]\\n<translation>` separated by blank lines, matching the input order:\n\n{numbered}"
                ),
            }],
        )
        text = resp.content[0].text  # type: ignore[attr-defined]
        translated = _parse_yaml_response(text, list(to_translate.keys()))
        new_data = dict(data)
        new_data.update(translated)

        dst_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dst_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(new_data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        created += 1
        print(f"Created {dst_path.relative_to(target_dir.parent)}", file=sys.stderr)

    print(f"Translated {created} YAML files.", file=sys.stderr)


def _parse_yaml_response(text: str, keys: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    current_key: str | None = None
    buf: list[str] = []

    def _flush():
        if current_key and current_key in keys:
            out[current_key] = "\n".join(buf).strip()

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            _flush()
            current_key = stripped[1:-1].strip()
            buf = []
        else:
            buf.append(line)
    _flush()
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    po = sub.add_parser("po", help="Translate missing entries in a .po file")
    po.add_argument("--source", required=True, type=Path)
    po.add_argument("--target", required=True, type=Path)
    po.add_argument("--language", required=True, help='e.g. "Simplified Chinese"')

    yml = sub.add_parser("yaml", help="Translate science YAML files")
    yml.add_argument("--source-dir", required=True, type=Path)
    yml.add_argument("--target-dir", required=True, type=Path)
    yml.add_argument("--language", required=True)

    args = p.parse_args()

    if args.cmd == "po":
        source_entries = parse_po(args.source)
        target_entries = parse_po(args.target) if args.target.exists() else []
        target_by_msgid = {e["msgid"]: e for e in target_entries}
        merged: list[dict] = []
        for e in source_entries:
            msgid = e["msgid"]
            existing = target_by_msgid.get(msgid)
            merged.append({
                "prefix_lines": e["prefix_lines"],
                "msgid": msgid,
                "msgstr": existing["msgstr"] if existing else "",
            })
        translate_batch(merged, args.language)
        args.target.parent.mkdir(parents=True, exist_ok=True)
        write_po(args.target, merged)
        print(f"Wrote {args.target}")
        return 0

    if args.cmd == "yaml":
        translate_yaml_tree(args.source_dir, args.target_dir, args.language)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
