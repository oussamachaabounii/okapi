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
    # Technical: how the code works.
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
    # Functional: what the product does for its users, in product terms.
    "Feature": "A user-facing capability: what it does, who it serves, the value it provides.",
    "User Journey": "How a user accomplishes a goal end-to-end, told in product terms (the functional counterpart of a Workflow).",
    "Business Rule": "A domain rule, policy, or constraint the code enforces, and why it exists.",
    "Domain Term": "A glossary entry: a domain word or concept the code embodies, defined in plain language.",
}

# Concept type vocabulary for scientific papers (`okapi analyze paper.pdf`),
# mirroring the two-lens split above: how the work was done vs what it means.
PAPER_CONCEPT_TYPES: dict[str, str] = {
    # Technical: how the work was done.
    "Paper": "The whole paper at a glance: question, approach, headline results (analog of System).",
    "Method": "A technique, algorithm, or model the paper proposes or relies on.",
    "Experiment": "An experimental setup: what was run, on what, measured how.",
    "Dataset": "Data the paper uses or introduces: source, size, structure.",
    "Result": "A reported result, quantitative or qualitative, exactly as stated.",
    "Related Work": "How the paper positions itself against prior art.",
    # Plain-language: what the work means, for readers outside the field.
    "Contribution": "What the authors claim is new, in one plain sentence each.",
    "Finding": "A takeaway in plain language: what was learned and how solid it is.",
    "Limitation": "A stated or evident limitation, and what it means for the claims.",
    "Domain Term": CONCEPT_TYPES["Domain Term"],
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
<project>-okf/
├── index.md            # bundle entry point: linked sections, no frontmatter
├── log.md              # dated changelog, no frontmatter
├── overview.md         # type: System — the whole-repo concept
├── entrypoints/        # one concept per way execution starts
│   └── index.md
├── modules/  services/ # whichever fits what the code actually contains
│   └── index.md
├── workflows/          # traced end-to-end flows
│   └── index.md
├── data-models/
│   └── index.md
└── functional/         # product-level knowledge: features, journeys, rules, glossary
    └── index.md
"""

# Starting shape for paper bundles — same caveat: a hint, not a requirement.
PAPER_BUNDLE_LAYOUT_HINT = """\
<paper>-okf/
├── index.md            # bundle entry point: linked sections, no frontmatter
├── log.md              # dated changelog, no frontmatter
├── overview.md         # type: Paper — the whole-paper concept
├── contributions/      # one concept per claimed contribution
│   └── index.md
├── methods/
│   └── index.md
├── experiments/        # setups, datasets, and results
│   └── index.md
├── findings/           # plain-language takeaways and limitations
│   └── index.md
├── glossary/           # Domain Term concepts
│   └── index.md
└── related-work.md     # type: Related Work
"""
