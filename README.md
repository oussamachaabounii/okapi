# okapi

Point `okapi` at a git repo, a package inside one, or a single file, and it
uses the [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview)
to reverse-engineer the code — reading it, tracing entry points, services,
data models, and workflows — and writes what it learns as a folder of markdown
files conforming to Google's [Open Knowledge Format (OKF v0.1)](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md).

## Install

Requires Python 3.10+. From the repo root:

```sh
pipx install .          # isolated install, recommended
# or
pip install -e .        # editable install for development
```

Either one puts a real `okapi` command on your PATH.

## Auth

okapi works out of the box with a **local Claude Code login** — if you already
use the `claude` CLI (subscription or otherwise), there is nothing to
configure; the Agent SDK reuses that session.

To bill through the **Anthropic API** instead, export a key — it takes
precedence over the local login when set:

```sh
export ANTHROPIC_API_KEY=sk-ant-...   # optional; see .env.example
```

`okapi analyze` prints which credential source it detected before running,
and fails fast with setup guidance if it finds neither.

## Usage

```sh
# Analyze a whole repo — writes <repo>/okf-knowledge/
okapi analyze ~/code/my-service

# A single file (the bundle still lands at the repo root)
okapi analyze ~/code/my-service/src/billing.py

# Narrow the scope
okapi analyze ~/code/my-service --focus "the payment flow"

# Exhaustive pass (quick | standard | deep)
okapi analyze ~/code/my-service --depth deep

# Pick the model: an alias (sonnet, opus, haiku) or any full model id
okapi analyze ~/code/my-service --model opus
okapi analyze ~/code/my-service --model claude-sonnet-4-6

# Check an existing (possibly hand-edited) bundle
okapi validate ~/code/my-service/okf-knowledge
```

Options for `analyze`: `-o/--output` (default `<repo_root>/okf-knowledge` — must
be inside the target repo, the agent's file tools are sandboxed to it),
`--include-tests/--no-include-tests` (default off), `--model` (default
`sonnet` → `claude-sonnet-5`; aliases: `sonnet`, `opus`, `haiku`; anything
else is passed to the SDK as-is).

Exit codes: `0` success, `1` user/config error or agent failure, `2` the bundle
failed OKF validation (offending files are listed; nothing is deleted).

## What the output looks like

```
okf-knowledge/
├── index.md            # entry point: linked sections, no frontmatter
├── log.md              # dated changelog, no frontmatter
├── overview.md         # type: system
├── entrypoints/
│   ├── index.md
│   └── cli.md
├── services/
│   ├── index.md
│   └── billing.md
└── workflows/
    ├── index.md
    └── invoice-lifecycle.md
```

Every concept file has YAML frontmatter in the style of [Google's OKF
examples](https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing):
`type` is required (a Title Case category like `Module` or `Entry Point`);
`title`, `description`, `tags`, `resource`, and `timestamp` (ISO 8601) are
always emitted — `resource` points back at the real source path. Bodies are
scannable sections that prefer markdown tables for anything enumerable
(schemas, signatures, CLI options), and relationships are plain markdown
links in the prose. After each run, `okapi analyze` automatically validates
the bundle and prints a pass/fail summary.

## Extending

- **New concept types** — add an entry to `CONCEPT_TYPES` in
  `src/okapi/okf_schema.py`. It's a flat dict on purpose: the validator only
  warns on unknown types, so nothing else needs touching.
- **Analysis behavior** — tune the prompts in `src/okapi/prompts.py`:
  `build_system_prompt()` encodes the OKF rules, `build_task_prompt()`
  describes a run, `DEPTH_PRESETS` controls scope and turn budgets.
- **Validation rules** — `src/okapi/validator.py`, tested against the
  fixtures in `tests/fixtures/tiny_bundle/`.

## Known limitations (v0.1)

- **Single-pass only** — every run regenerates the bundle from scratch; there
  is no incremental `--update` yet (the prompt builder already accepts an
  `existing_bundle` argument to support it later).
- No visualizer (`okapi visualize`) or MCP server mode yet.
- The validator checks structure and frontmatter, not whether the prose is
  accurate — skim the bundle after a run.

## Development

```sh
pip install -e ".[dev]"
pytest
```
