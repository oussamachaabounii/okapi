"""okapi command-line interface.

Exit codes: 0 success, 1 user/config error (bad path, missing API key,
agent failure), 2 validation failure.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console

from . import __version__
from .agent import (
    DEFAULT_MODEL,
    MODEL_ALIASES,
    detect_auth,
    resolve_paths,
    run_analysis,
)
from .prompts import DEPTH_PRESETS
from .validator import ValidationReport, validate_bundle

console = Console()


def _render_report(report: ValidationReport, bundle: Path) -> None:
    console.print(f"\n[bold]validate[/] {bundle}: {report.concept_count} concept(s)")
    for warning in report.warnings:
        console.print(f"  [yellow]warn[/]  {warning}")
    for error in report.errors:
        console.print(f"  [red]error[/] {error}")
    if report.ok:
        console.print("  [green]OK[/] — bundle conforms to OKF v0.1")
    else:
        console.print(f"  [red]FAILED[/] — {len(report.errors)} error(s)")


@click.group()
@click.version_option(version=__version__, prog_name="okapi")
def main() -> None:
    """Reverse-engineer a codebase into an OKF v0.1 knowledge bundle."""


@main.command()
@click.argument("target", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o", "--output", "output_dir", type=click.Path(path_type=Path), default=None,
    help="Bundle directory [default: <repo_root>/okf-knowledge].",
)
@click.option(
    "--depth", type=click.Choice(sorted(DEPTH_PRESETS)), default="standard",
    show_default=True, help="How exhaustive the analysis should be.",
)
@click.option(
    "--focus", default=None,
    help='Narrow the analysis, e.g. a module name or "the payment flow".',
)
@click.option(
    "--include-tests/--no-include-tests", default=False, show_default=True,
    help="Whether to document the test suite as well.",
)
@click.option(
    "--model", default=DEFAULT_MODEL, show_default=True,
    help="Claude model: an alias ({}) or any full model id.".format(
        ", ".join(f"{k} = {v}" for k, v in MODEL_ALIASES.items())
    ),
)
def analyze(
    target: Path,
    output_dir: Path | None,
    depth: str,
    focus: str | None,
    include_tests: bool,
    model: str,
) -> None:
    """Analyze TARGET (repo, directory, or file) and write an OKF bundle."""
    try:
        auth = detect_auth()
    except RuntimeError as exc:
        console.print(f"[red]error:[/] {exc}")
        sys.exit(1)
    console.print(f"[dim]auth: {auth.detail}[/]")

    try:
        _, resolved_target, resolved_output = resolve_paths(target, output_dir)
    except ValueError as exc:
        console.print(f"[red]error:[/] {exc}")
        sys.exit(1)

    try:
        result = asyncio.run(
            run_analysis(
                resolved_target,
                resolved_output,
                depth=depth,
                focus=focus,
                include_tests=include_tests,
                model=model,
                console=console,
            )
        )
    except Exception as exc:  # e.g. Claude Code CLI missing or failed to start
        console.print(f"[red]error:[/] {exc}")
        sys.exit(1)

    report = validate_bundle(result.output_dir)
    _render_report(report, result.output_dir)

    if not result.success:
        sys.exit(1)
    if not report.ok:
        # Offending files are already listed; never delete anything.
        sys.exit(2)
    console.print(
        f"\n[dim]explore it visually:[/] okapi visualize {result.output_dir} --open"
    )


@main.command()
@click.argument("bundle_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
def validate(bundle_dir: Path) -> None:
    """Check an existing OKF bundle for conformance."""
    report = validate_bundle(bundle_dir)
    _render_report(report, bundle_dir)
    if not report.ok:
        sys.exit(2)


@main.command()
@click.argument("bundle_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "-o", "--output", "output_file", type=click.Path(path_type=Path), default=None,
    help="Where to write the HTML [default: <bundle>/okf-viewer.html].",
)
@click.option("--open", "open_browser", is_flag=True, help="Open the page in your browser.")
def visualize(bundle_dir: Path, output_file: Path | None, open_browser: bool) -> None:
    """Render BUNDLE_DIR as an interactive knowledge-graph HTML page."""
    from .visualizer import build_visualization

    try:
        out = build_visualization(bundle_dir, output_file)
    except ValueError as exc:
        console.print(f"[red]error:[/] {exc}")
        sys.exit(1)
    console.print(f"[green]viewer written:[/] {out}")
    if open_browser:
        import webbrowser

        webbrowser.open(out.resolve().as_uri())


if __name__ == "__main__":
    main()
