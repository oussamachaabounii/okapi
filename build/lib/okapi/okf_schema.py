"""OKF v0.1 vocabulary shared by the prompt builders and the validator.

Spec: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
Keep this in sync with the rules encoded in prompts.build_system_prompt().
"""

# Concept type vocabulary. Human-readable Title Case strings, following the
# convention in Google's OKF examples ("BigQuery Table", "Metric", "Playbook").
# Deliberately a flat dict (not an enum) so new types can be added without
# touching validator logic — the validator only *warns* on unknown types
# (case-insensitively), it never fails on them.
CONCEPT_TYPES: dict[str, str] = {
    "System": "The whole system/repo at a glance: purpose, boundaries, tech stack.",
    "Service": "A deployable or independently-running component (API, worker, daemon).",
    "Module": "A cohesive code unit inside a service: package, namespace, layer.",
    "Entry Point": "Where execution starts: main functions, CLI commands, HTTP routes, handlers.",
    "Workflow": "A multi-step process traced through the code: request flow, job pipeline, lifecycle.",
    "Data Model": "A core domain entity or schema: DB table, message shape, config format.",
    "Interface": "A contract between parts: public API surface, protocol, event topic.",
    "Dependency": "A load-bearing external system or library and how the code relies on it.",
    "Convention": "A recurring pattern or house rule the codebase follows.",
    "Decision": "An inferred or documented architectural decision and its rationale.",
}

# Filenames reserved by OKF at any directory level — never valid concept names.
# index.md: linked sections for progressive disclosure, no frontmatter.
# log.md: dated changelog, no frontmatter.
RESERVED_FILENAMES: frozenset[str] = frozenset({"index.md", "log.md"})

# The only field OKF v0.1 *requires* in concept frontmatter.
REQUIRED_FIELDS: tuple[str, ...] = ("type",)

# Fields this tool always emits and the validator warns about when missing.
# `resource` points back at the real source the concept documents;
# `timestamp` is the last-update time as an ISO 8601 datetime.
RECOMMENDED_FIELDS: tuple[str, ...] = ("title", "description", "tags", "resource", "timestamp")

# A structural hint given to the agent. OKF mandates no fixed taxonomy —
# structure should fit what's actually found in the target — so this is a
# starting shape, not a requirement.
BUNDLE_LAYOUT_HINT = """\
okf-knowledge/
├── index.md            # bundle entry point: linked sections, no frontmatter
├── log.md              # dated changelog, no frontmatter
├── overview.md         # type: System — the whole-repo concept
├── entrypoints/        # one concept per way execution starts
│   └── index.md
├── modules/  services/ # whichever fits what the code actually contains
│   └── index.md
├── workflows/          # traced end-to-end flows
│   └── index.md
└── data-models/
    └── index.md
"""
