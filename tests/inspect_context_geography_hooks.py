from pathlib import Path

ROOT = Path(r"D:\YouTubeTools\AI_Video_Editor")

PATTERNS = [
    "primary_keyword",
    "BATCH COMPLETE",
    "KieAIProvider",
    "analysis",
    "search_manager.search_scene",
    "visual_ranker.rank",
]

SKIP_DIRS = {
    "venv",
    ".git",
    "__pycache__",
    "build",
    "dist",
}


def should_skip(path):
    return any(
        part.lower() in SKIP_DIRS
        for part in path.parts
    )


print("=" * 80)
print("AI VIDEO EDITOR - CONTEXT / GEOGRAPHY HOOK INSPECTOR")
print("=" * 80)

matches = []

for path in ROOT.rglob("*.py"):

    if should_skip(path):
        continue

    try:
        text = path.read_text(
            encoding="utf-8",
            errors="ignore",
        )
    except Exception:
        continue

    found = []

    for pattern in PATTERNS:

        if pattern.lower() in text.lower():
            found.append(pattern)

    if found:
        matches.append(
            (path, found)
        )


for path, found in matches:

    print()
    print("-" * 80)
    print("FILE:", path)
    print("MATCHES:", ", ".join(found))

    lines = path.read_text(
        encoding="utf-8",
        errors="ignore",
    ).splitlines()

    interesting = []

    for i, line in enumerate(lines):

        if any(
            pattern.lower()
            in line.lower()
            for pattern in PATTERNS
        ):
            interesting.append(i)

    printed = set()

    for hit in interesting:

        start = max(
            0,
            hit - 8,
        )

        end = min(
            len(lines),
            hit + 15,
        )

        for i in range(
            start,
            end,
        ):

            if i in printed:
                continue

            printed.add(i)

            print(
                f"{i + 1}: "
                f"{lines[i]}"
            )

        print()


print()
print("=" * 80)
print("INSPECTION COMPLETE")
print("=" * 80)