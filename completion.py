"""Pure Lean abbreviation completion logic, with LSP UTF-16 coordinates."""
import json
from pathlib import Path

TABLE = json.loads((Path(__file__).parent / "data" / "abbreviations.json").read_text(encoding="utf-8"))
KEYS = sorted(TABLE)


def units(text):
    return len(text.encode("utf-16-le")) // 2


def index_at(line, character):
    if not isinstance(character, int) or isinstance(character, bool) or character < 0:
        raise ValueError("invalid character")
    count = 0
    for i, char in enumerate(line):
        if count == character:
            return i
        count += units(char)
        if count > character:
            raise ValueError("position inside surrogate pair")
    if count == character:
        return len(line)
    raise ValueError("position past line")


def snippet(value):
    # Escape only snippet metacharacters in literal portions.
    parts = value.split("$CURSOR")
    return "$0".join(p.replace("\\", "\\\\").replace("$", "\\$").replace("}", "\\}") for p in parts)


def complete(text, position, snippets=False):
    lines = text.split("\n")
    line_no = position.get("line")
    if not isinstance(line_no, int) or isinstance(line_no, bool) or not 0 <= line_no < len(lines):
        raise ValueError("invalid line")
    line = lines[line_no].removesuffix("\r")
    cursor = index_at(line, position.get("character"))
    # Try each leader from left to right. A backslash can itself be part of a key.
    for start in range(cursor):
        if line[start] != "\\":
            continue
        prefix = line[start + 1:cursor]
        matches = [key for key in KEYS if key.startswith(prefix)]
        if not matches:
            continue
        # Candidate membership and exact-first ordering depend only on text left of the cursor.
        prefix = line[start + 1:cursor]
        matches.sort(key=lambda k: (k != prefix, k))
        items = []
        for key in matches:
            # Consume the longest contiguous right prefix compatible with this candidate.
            end = cursor
            while end < len(line) and key.startswith(line[start + 1:end + 1]):
                end += 1
            span = {"start": {"line": line_no, "character": units(line[:start])},
                    "end": {"line": line_no, "character": units(line[:end])}}
            value = TABLE[key]
            new_text = snippet(value) if snippets else value.replace("$CURSOR", "")
            items.append({"label": "\\" + key, "filterText": "\\" + key,
                          "sortText": ("0" if key == prefix else "1") + key,
                          "detail": value.replace("$CURSOR", ""),
                          "insertTextFormat": 2 if snippets else 1,
                          "textEdit": {"range": span, "newText": new_text}})
        return items
    return []
