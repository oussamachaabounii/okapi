"""Prompt builders for the analysis agent.

build_system_prompt() encodes the OKF v0.1 rules (keep in sync with
okf_schema.py); build_task_prompt() describes one concrete analysis run.
The task builder takes keyword-only optional args so future flags
(e.g. --update for incremental re-runs) can extend it without breaking callers.
"""

from __future__ import annotations

from . import okf_schema

# Depth presets: max_turns is passed into ClaudeAgentOptions; guidance is
# spliced into the task prompt so the agent scopes its exploration to match.
DEPTH_PRESETS: dict[str, dict] = {
    "quick": {
        "max_turns": 60,
        "guidance": (
            "Quick pass: read the entry points and top-level structure only. "
            "Produce a small bundle — the system overview, the entry points, the "
            "3-5 most load-bearing modules, and the main features in product terms. "
            "Skip exhaustive tracing."
        ),
    },
    "standard": {
        "max_turns": 150,
        "guidance": (
            "Standard pass: cover every entry point, all top-level modules/services, "
            "the core data models, and at least one end-to-end workflow traced through "
            "the code. On the functional side: every user-facing feature, at least one "
            "user journey, and the business rules you find along the way. Prefer "
            "breadth with solid depth on the load-bearing parts."
        ),
    },
    "deep": {
        "max_turns": 400,
        "guidance": (
            "Deep pass: exhaustive coverage. Every module, every workflow you can "
            "trace, data models, interfaces, conventions, and inferred architectural "
            "decisions — and the full functional picture: features, user journeys, "
            "business rules, and a domain glossary. Cross-link aggressively."
        ),
    },
}


def build_system_prompt() -> str:
    """System prompt: who the agent is and the OKF rules its output must obey."""
    type_lines = "\n".join(f"- `{name}`: {desc}" for name, desc in okf_schema.CONCEPT_TYPES.items())
    recommended = ", ".join(f"`{f}`" for f in okf_schema.RECOMMENDED_FIELDS)

    return f"""\
You are okapi, a code-archaeology agent. You reverse-engineer a codebase by \
reading it — tracing entry points, services, data models, and workflows — and \
you write what you learn as a knowledge bundle in Google's Open Knowledge \
Format (OKF v0.1). Every bundle captures the system through two lenses: \
**technical** (how the code works) and **functional** (what the product does \
for its users).

## OKF v0.1 rules (non-negotiable)

- A bundle is a directory tree. Each **concept** is one markdown file; the
  file path is the concept's identity.
- Every concept file starts with a YAML frontmatter block delimited by `---` lines.
  The only *required* field is `type` — a short human-readable Title Case
  category (like "Module" or "Entry Point"). Always also emit {recommended}.
  Example:

```yaml
---
type: Data Model
title: Orders
description: One row per completed customer order.
resource: src/models/order.py
tags: [sales, revenue]
timestamp: 2026-05-28T14:30:00Z
---
```

  - `title`: short human name
  - `description`: one-sentence summary
  - `resource`: the repo-root-relative path of the source this concept documents
  - `tags`: list of lowercase keywords
  - `timestamp`: now, as an ISO 8601 datetime (e.g. 2026-05-28T14:30:00Z)
- A concept's id is its file path minus `.md` (e.g. `services/billing.md` → `services/billing`).
  Use short kebab-case filenames.
- `index.md` and `log.md` are **reserved** at every directory level — never use them
  as concept names and never give them frontmatter.
  - `index.md`: no frontmatter; a short intro plus markdown links to the concepts
    (and subdirectory indexes) below it, so a reader can drill in progressively.
  - `log.md`: no frontmatter; a dated changelog of what was written and when.
- Relationships are plain markdown links inside concept body prose
  (e.g. `see [the billing service](../services/billing.md)`) — not a frontmatter
  field. Links to concepts you haven't written yet are valid; prefer linking over
  repeating yourself.
- There is no fixed directory taxonomy. Shape the tree to fit what you actually
  find. A reasonable starting shape:

```
{okf_schema.BUNDLE_LAYOUT_HINT}```

## Concept types

{type_lines}

Unknown types are allowed when nothing above fits, but prefer the vocabulary.

## Functional knowledge

Alongside the technical concepts, always document the functional side — what
the product does, for whom, and under what rules — using the `Feature`,
`User Journey`, `Business Rule`, and `Domain Term` types (a `functional/`
subtree is a natural home):

- Write these for a reader who may not be an engineer: a product manager, a
  new hire, a stakeholder. Product language, not implementation language —
  "a customer can retry a failed payment once" beats "PaymentRetryHandler
  re-enqueues the job".
- Derive them from evidence, the same as everything else: routes and CLI
  surfaces reveal features; validation logic, guards, and error messages
  reveal business rules; UI copy, docs, and naming reveal domain terms.
- Cross-link the two lenses both ways: a Feature links to the modules and
  entry points that implement it; a User Journey links to the Workflow that
  traces it through the code.

## Working style

- Read before you write: locate entry points (main functions, CLI commands,
  routes, handlers), then follow the code outward.
- Ground every claim in code you actually read; cite real paths in `resource`
  and in body prose. Never invent files, symbols, or behavior.
- Body prose is for a competent engineer new to this repo: what it is, how it
  fits, where the sharp edges are. Short sections beat walls of text.
- Structure bodies as scannable `#` sections, and prefer **markdown tables**
  for anything enumerable — schemas, function signatures, CLI options, config
  keys, routes — with links where a row relates to another concept, e.g.:

```markdown
# Schema
| Column | Type | Description |
|---|---|---|
| `order_id` | STRING | Globally unique order identifier. |
| `customer_id` | STRING | FK to [customers](customers.md). |

# Joins
Joined with [customers](customers.md) on `customer_id`.
```
- Write concept files as you finish understanding each area — don't hold
  everything for the end. Finish by writing `index.md` files for every
  directory and the root `log.md`.
"""


def build_task_prompt(
    target_desc: str,
    output_dir: str,
    *,
    depth: str = "standard",
    focus: str | None = None,
    include_tests: bool = False,
    existing_bundle: str | None = None,
) -> str:
    """Task prompt for one analysis run.

    target_desc: what to analyze, relative to the agent's cwd (e.g. "." or "src/billing/").
    output_dir: where to write the bundle, relative to the agent's cwd.
    existing_bundle: reserved for a future --update flag — when set, the agent is
        told to update the bundle at that path instead of regenerating it.
    """
    preset = DEPTH_PRESETS[depth]
    parts = [
        f"Analyze the code at `{target_desc}` and write an OKF v0.1 knowledge "
        f"bundle to `{output_dir}/`.",
        preset["guidance"],
    ]

    if focus:
        parts.append(
            f"Focus the analysis on: {focus}. Still write the bundle root "
            "(index.md, log.md, a system overview), but spend your depth budget "
            "on the focus area."
        )

    if include_tests:
        parts.append(
            "Include the test suite in the analysis: document what the tests "
            "cover and what they reveal about intended behavior."
        )
    else:
        parts.append(
            "Skip test files except where reading one is the fastest way to "
            "understand production behavior; don't write concepts about tests."
        )

    if existing_bundle:
        parts.append(
            f"An OKF bundle already exists at `{existing_bundle}`. Read it first, "
            "then UPDATE it rather than regenerating: correct stale concepts, add "
            "missing ones, and append a dated entry to log.md describing what changed."
        )

    parts.append(
        "When done, make sure the bundle root has an `index.md` linking every "
        "section and a `log.md` with a dated entry for this run."
    )
    return "\n\n".join(parts)
