"""Orchestrates the Claude Agent SDK call that performs the analysis."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)
from rich.console import Console

from . import prompts

# Friendly names → model ids. Any string not in this map is passed through
# to the SDK untouched, so full ids (or future models) always work.
MODEL_ALIASES: dict[str, str] = {
    "sonnet": "claude-sonnet-5",
    "opus": "claude-opus-4-8",
    "haiku": "claude-haiku-4-5",
}

DEFAULT_MODEL = "sonnet"

ALLOWED_TOOLS = ["Read", "Glob", "Grep", "Write", "Bash"]


def resolve_model(name: str) -> str:
    return MODEL_ALIASES.get(name.strip().lower(), name)


@dataclass
class AuthInfo:
    mode: str    # "api-key" | "claude-code"
    detail: str  # human-readable, shown to the user


def detect_auth() -> AuthInfo:
    """Figure out how the Agent SDK will authenticate.

    Precedence mirrors the SDK itself: an ANTHROPIC_API_KEY wins (direct API
    billing); otherwise the SDK spawns the local Claude Code CLI, which uses
    its own login (subscription or previously saved credentials). Raises
    RuntimeError with setup guidance when neither is available.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        return AuthInfo("api-key", "ANTHROPIC_API_KEY (Anthropic API)")
    if shutil.which("claude") or (Path.home() / ".claude").exists():
        return AuthInfo("claude-code", "local Claude Code login")
    raise RuntimeError(
        "no credentials found. Either log in to Claude Code (`claude` then "
        "/login — okapi reuses that session), or export ANTHROPIC_API_KEY "
        "(see .env.example) to use the API directly."
    )


@dataclass
class AnalysisResult:
    target: Path
    output_dir: Path
    summary: str
    message_count: int
    success: bool


def find_repo_root(start: Path) -> Path:
    """Walk up from `start` looking for a .git directory; fall back to `start`
    itself (or its parent when `start` is a file)."""
    base = start if start.is_dir() else start.parent
    for candidate in (base, *base.parents):
        if (candidate / ".git").exists():
            return candidate
    return base


def default_bundle_dir(target: Path) -> Path:
    """Default bundle location: `<name>-okf` inside the analyzed directory
    (or the file's directory when the target is a file), named after it —
    e.g. analyzing `maqam/` yields `maqam/maqam-okf`."""
    base = target if target.is_dir() else target.parent
    return base / f"{base.name}-okf"


def resolve_paths(target: Path, output_dir: Path | None) -> tuple[Path, Path, Path]:
    """Resolve (cwd, target, output_dir) for the SDK call.

    cwd is the repo root containing the target (the SDK sandboxes file tools to
    cwd and below, so the output dir must live under it). Raises ValueError if
    an explicit output_dir falls outside cwd.
    """
    target = target.resolve()
    cwd = find_repo_root(target)

    if output_dir is None:
        output_dir = default_bundle_dir(target)
    output_dir = output_dir.resolve()

    if not output_dir.is_relative_to(cwd):
        raise ValueError(
            f"output directory {output_dir} is outside the analysis root {cwd}; "
            "the agent's file tools are sandboxed to the target repo, so the "
            "bundle must be written inside it (or omit -o to use the default "
            f"{default_bundle_dir(target)})"
        )
    return cwd, target, output_dir


def _describe_tool_use(block: ToolUseBlock) -> str:
    inp = block.input or {}
    detail = inp.get("file_path") or inp.get("path") or inp.get("pattern") or inp.get("command") or ""
    detail = str(detail)
    if len(detail) > 80:
        detail = detail[:77] + "..."
    return f"[bold cyan]{block.name}[/] {detail}".rstrip()


async def run_analysis(
    target: Path,
    output_dir: Path,
    *,
    depth: str = "standard",
    focus: str | None = None,
    include_tests: bool = False,
    model: str = DEFAULT_MODEL,
    console: Console | None = None,
) -> AnalysisResult:
    """Run one analysis pass over `target`, writing the bundle to `output_dir`.

    `target` and `output_dir` should come from resolve_paths() so the sandbox
    invariant (output under the repo root) already holds.
    """
    console = console or Console()
    model = resolve_model(model)
    cwd, target, output_dir = resolve_paths(target, output_dir)

    target_desc = "." if target == cwd else str(target.relative_to(cwd))
    output_desc = str(output_dir.relative_to(cwd))

    options = ClaudeAgentOptions(
        cwd=str(cwd),
        allowed_tools=ALLOWED_TOOLS,
        permission_mode="acceptEdits",
        system_prompt=prompts.build_system_prompt(),
        model=model,
        max_turns=prompts.DEPTH_PRESETS[depth]["max_turns"],
    )
    task_prompt = prompts.build_task_prompt(
        target_desc,
        output_desc,
        depth=depth,
        focus=focus,
        include_tests=include_tests,
    )

    console.print(f"[bold]okapi[/] analyzing [green]{target}[/]")
    console.print(f"  root: {cwd}   depth: {depth}   model: {model}")
    console.print(f"  bundle: {output_dir}\n")

    message_count = 0
    files_written: set[str] = set()
    result_msg: ResultMessage | None = None
    run_error: str | None = None

    with console.status("starting agent...", spinner="dots") as status:
        try:
            async for message in query(prompt=task_prompt, options=options):
                message_count += 1
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, ToolUseBlock):
                            status.update(_describe_tool_use(block))
                            if block.name == "Write":
                                written = str((block.input or {}).get("file_path", ""))
                                if written:
                                    files_written.add(written)
                                    console.print(f"  [dim]wrote[/] {written}")
                        elif isinstance(block, TextBlock) and block.text.strip():
                            # Show the first line of the agent's narration as status.
                            status.update(f"[dim]{block.text.strip().splitlines()[0][:100]}[/]")
                elif isinstance(message, ResultMessage):
                    result_msg = message
        except Exception as exc:
            # The SDK raises mid-stream when the CLI process exits with an
            # error (e.g. the turn budget ran out). Whatever was written so
            # far is still on disk — report the failure, don't traceback.
            run_error = str(exc)

    success = (
        result_msg is not None
        and not getattr(result_msg, "is_error", False)
        and run_error is None
    )
    if run_error:
        hint = ""
        if "max_turns" in run_error or "success" in run_error:
            hint = " (likely ran out of turns — try a deeper --depth or a narrower --focus)"
        console.print(f"[red]agent run aborted:[/] {run_error}{hint}")
    turns = getattr(result_msg, "num_turns", None) if result_msg else None
    cost = getattr(result_msg, "total_cost_usd", None) if result_msg else None

    summary_bits = [f"{len(files_written)} file(s) written"]
    if turns is not None:
        summary_bits.append(f"{turns} turns")
    if cost is not None:
        summary_bits.append(f"${cost:.4f}")
    summary = ", ".join(summary_bits)

    console.print()
    style = "green" if success else "red"
    console.print(f"[{style}]{'done' if success else 'agent reported an error'}[/] — {summary}")

    return AnalysisResult(
        target=target,
        output_dir=output_dir,
        summary=summary,
        message_count=message_count,
        success=success,
    )
