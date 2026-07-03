"""Post-hoc OKF v0.1 conformance checker.

Deliberately dependency-light: frontmatter is split on the `---` delimiters
and parsed with yaml.safe_load — no markdown parser involved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import okf_schema


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    concept_count: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors


def _parse_frontmatter(text: str) -> dict | None:
    """Return the frontmatter mapping, or None if the file has no frontmatter
    block. Raises ValueError on a malformed block (unterminated or non-mapping).
    """
    if not text.startswith("---\n") and text.strip() != "---":
        return None
    # Find the closing delimiter: a line that is exactly "---".
    lines = text.split("\n")
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            block = "\n".join(lines[1:i])
            data = yaml.safe_load(block)
            if data is None:
                return {}
            if not isinstance(data, dict):
                raise ValueError("frontmatter is not a YAML mapping")
            return data
    raise ValueError("unterminated frontmatter block (missing closing '---')")


def validate_bundle(path: Path) -> ValidationReport:
    """Walk an OKF bundle and check every markdown file against the v0.1 rules."""
    report = ValidationReport()
    path = Path(path)

    if not path.is_dir():
        report.errors.append(f"{path}: not a directory")
        return report

    md_files = sorted(path.rglob("*.md"))
    if not md_files:
        report.errors.append(f"{path}: no markdown files found — not an OKF bundle")
        return report

    dirs_with_md: set[Path] = set()

    for md in md_files:
        rel = md.relative_to(path)
        dirs_with_md.add(md.parent)
        try:
            text = md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            report.errors.append(f"{rel}: unreadable ({exc})")
            continue

        try:
            fm = _parse_frontmatter(text)
        except ValueError as exc:
            report.errors.append(f"{rel}: {exc}")
            continue

        if md.name in okf_schema.RESERVED_FILENAMES:
            # Reserved files must NOT carry frontmatter — concept content in
            # index.md/log.md is a spec violation.
            if fm is not None:
                report.errors.append(
                    f"{rel}: reserved filename must not have frontmatter "
                    "(concept content belongs in its own file)"
                )
            continue

        # Everything else is a concept file.
        if fm is None:
            report.errors.append(f"{rel}: concept file is missing frontmatter")
            continue

        report.concept_count += 1

        for required in okf_schema.REQUIRED_FIELDS:
            if required not in fm:
                report.errors.append(f"{rel}: missing required field '{required}'")

        known_types = {t.lower() for t in okf_schema.CONCEPT_TYPES}
        if "type" in fm and str(fm["type"]).lower() not in known_types:
            report.warnings.append(
                f"{rel}: type '{fm['type']}' is not in the known vocabulary"
            )

        missing = [f for f in okf_schema.RECOMMENDED_FIELDS if f not in fm]
        if missing:
            report.warnings.append(
                f"{rel}: missing recommended field(s): {', '.join(missing)}"
            )

    # OKF marks index.md optional, but for this tool's output it should be
    # the norm — warn per directory that holds markdown without one.
    for directory in sorted(dirs_with_md):
        if not (directory / "index.md").exists():
            rel_dir = directory.relative_to(path)
            label = "." if str(rel_dir) == "." else str(rel_dir)
            report.warnings.append(f"{label}/: no index.md")

    return report
