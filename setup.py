"""
Reads settings.toml and:
  1. Auto-fills release_date with today if empty
  2. Replaces <<<PLACEHOLDER>>> values in base docs and mkdocs.yml
  3. Creates stub .md files for each keyword in additional_pages
  4. Adds additional pages to mkdocs.yml nav (<<<ADDITIONAL_NAV>>>)
  5. Adds additional page links to index.md nav table (<<<ADDITIONAL_NAV_TABLE>>>)
  6. Reports remaining unfilled placeholders

Run once after copying the template: python setup.py
Re-running is safe — existing stubs are not overwritten.
"""

import sys
import os
import re
from datetime import date
from pathlib import Path

if sys.version_info < (3, 11):
    sys.exit("Python 3.11+ required (uses built-in tomllib).")

import tomllib


# ── Helpers ───────────────────────────────────────────────────────────────────

def slug(keyword: str) -> str:
    """'open camera laptop' → 'open-camera-laptop'"""
    return re.sub(r"\s+", "-", keyword.strip().lower())


def nav_title(keyword: str) -> str:
    """'open camera laptop' → 'Open Camera Laptop'"""
    return keyword.strip().title()


# ── Settings ──────────────────────────────────────────────────────────────────

def load_settings(path: Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def autofill_release_date(settings_path: Path, p: dict) -> str:
    """Write today's date into settings.toml if release_date is empty. Returns the date."""
    release_date = p.get("release_date", "").strip()
    if not release_date:
        release_date = date.today().isoformat()
        raw = settings_path.read_text(encoding="utf-8")
        raw = re.sub(r'(release_date\s*=\s*)"[^"]*"', f'\\1"{release_date}"', raw)
        settings_path.write_text(raw, encoding="utf-8")
        print(f"Auto-filled release_date = {release_date}")
    return release_date


def build_replacements(p: dict, release_date: str) -> dict:
    repo_name = Path(os.getcwd()).name
    return {
        "<<<APP_NAME>>>":                       p["app_name"],
        "<<<SHORT_DESCRIPTION>>>":              p.get("short_description", ""),
        "<<<META_DESCRIPTION_150_300_CHARS>>>": p.get("meta_description", ""),
        "<<<MAIN_KEYWORD>>>":                   p["main_keyword"],
        "<<<RELEASE_DATE>>>":                   release_date,
        "<<<REPO_NAME>>>":                      repo_name,
        "<<<RTFD_SLUG>>>":                      repo_name,
    }


def validate(replacements: dict) -> list[str]:
    return [k for k, v in replacements.items() if not v.strip()]


# ── File operations ───────────────────────────────────────────────────────────

def replace_in_file(path: Path, replacements: dict) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


# ── Additional pages ──────────────────────────────────────────────────────────

def make_stub(keyword: str, app_name: str, main_keyword: str, all_keywords: list[str]) -> str:
    """Generate a stub .md for an additional_pages keyword."""
    title = nav_title(keyword)

    other_rows = "\n".join(
        f"| [{nav_title(kw)}]({slug(kw)}.md) | {app_name} on {nav_title(kw).split()[-1]} |"
        for kw in all_keywords
        if kw != keyword
    )

    return f"""---
description: <!-- 150-300 chars about {title} for {app_name} — fill with LLM -->
---

# {title}

<!-- LLM PROMPT:
     Write 2-3 paragraphs about using {app_name} on {keyword}.
     Target keyword: "{keyword}". Also include "{main_keyword}" naturally.
     Audience: someone searching for "{keyword}" who wants to download or use the app. -->

## How to Use {app_name} on {nav_title(keyword).split()[-1]}

<!-- LLM: Step-by-step guide specific to this platform/context. 4-6 steps. -->

## Frequently Asked Questions

<!-- LLM: 3-5 Q&A pairs specific to "{keyword}". -->

---

## See Also

| Page | What you'll find |
|------|-----------------|
| [Home](index.md) | {app_name} overview |
| [Features](features.md) | Full list of features |
| [How to Download](how-to-download.md) | Download and setup guide |
| [FAQ](faq.md) | General FAQ |
{other_rows}
"""


def create_additional_pages(docs_dir: Path, additional_pages: list[str],
                             app_name: str, main_keyword: str) -> list[str]:
    created = []
    for kw in additional_pages:
        page_path = docs_dir / f"{slug(kw)}.md"
        if not page_path.exists():
            page_path.write_text(
                make_stub(kw, app_name, main_keyword, additional_pages),
                encoding="utf-8"
            )
            created.append(page_path.name)
    return created


# ── Nav injection ─────────────────────────────────────────────────────────────

def inject_nav(mkdocs_path: Path, additional_pages: list[str]) -> bool:
    """Replace <<<ADDITIONAL_NAV>>> in mkdocs.yml with generated nav lines."""
    text = mkdocs_path.read_text(encoding="utf-8")
    if "<<<ADDITIONAL_NAV>>>" not in text:
        return False
    nav_lines = "\n".join(
        f"  - {nav_title(kw)}: {slug(kw)}.md"
        for kw in additional_pages
    )
    mkdocs_path.write_text(text.replace("<<<ADDITIONAL_NAV>>>", nav_lines), encoding="utf-8")
    return True


def inject_nav_table(index_path: Path, additional_pages: list[str]) -> bool:
    """Replace <<<ADDITIONAL_NAV_TABLE>>> in index.md with table rows."""
    text = index_path.read_text(encoding="utf-8")
    if "<<<ADDITIONAL_NAV_TABLE>>>" not in text:
        return False
    rows = "\n".join(
        f"| [{nav_title(kw)}]({slug(kw)}.md) | Platform-specific guide |"
        for kw in additional_pages
    )
    index_path.write_text(text.replace("<<<ADDITIONAL_NAV_TABLE>>>", rows), encoding="utf-8")
    return True


# ── Main ──────────────────────────────────────────────────────────────────────

BASE_FILES = [
    "mkdocs.yml",
    "docs/index.md",
    "docs/features.md",
    "docs/how-to-download.md",
    "docs/faq.md",
]


def main():
    root = Path(__file__).parent
    settings_path = root / "settings.toml"

    if not settings_path.exists():
        sys.exit("ERROR: settings.toml not found.")

    settings = load_settings(settings_path)
    p = settings["project"]
    # additional_pages can be under [project] or at top level
    additional_pages = p.get("additional_pages") or settings.get("additional_pages", [])

    # 1. Auto-fill release_date
    release_date = autofill_release_date(settings_path, p)

    # 2. Build replacements and validate
    replacements = build_replacements(p, release_date)
    empty = validate(replacements)
    if empty:
        print("WARNING: empty fields in settings.toml:")
        for k in empty:
            print(f"  {k}")
        print()

    # 3. Create additional page stubs
    docs_dir = root / "docs"
    if additional_pages:
        created = create_additional_pages(docs_dir, additional_pages, p["app_name"], p["main_keyword"])
        if created:
            print("Created stubs:")
            for f in created:
                print(f"  docs/{f}")

    # 4. Inject nav entries into mkdocs.yml
    if additional_pages and inject_nav(root / "mkdocs.yml", additional_pages):
        print("Updated mkdocs.yml nav.")

    # 5. Inject nav table rows into index.md
    if additional_pages and inject_nav_table(docs_dir / "index.md", additional_pages):
        print("Updated index.md Quick Navigation table.")

    # 6. Replace placeholders in all files
    target_files = BASE_FILES + [f"docs/{slug(kw)}.md" for kw in additional_pages]
    changed = []
    for rel in target_files:
        path = root / rel
        if not path.exists():
            print(f"SKIP (not found): {rel}")
            continue
        if replace_in_file(path, replacements):
            changed.append(rel)

    if changed:
        print("Placeholders replaced in:")
        for f in changed:
            print(f"  {f}")
    else:
        print("Nothing to replace — all placeholders already filled.")

    # 7. Report remaining unfilled placeholders
    all_files = list(docs_dir.glob("*.md")) + [root / "mkdocs.yml"]
    remaining = []
    for path in all_files:
        if path.exists():
            found = re.findall(r"<<<\w+>>>", path.read_text(encoding="utf-8"))
            if found:
                remaining.append((path.relative_to(root), sorted(set(found))))

    if remaining:
        print("\nRemaining placeholders (fill with LLM):")
        for f, items in remaining:
            print(f"  {f}: {', '.join(items)}")
    else:
        print("\nAll placeholders filled. Ready to publish.")


if __name__ == "__main__":
    main()
