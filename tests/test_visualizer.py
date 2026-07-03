from pathlib import Path

import pytest

from okapi.visualizer import build_visualization, load_bundle

FIXTURES = Path(__file__).parent / "fixtures" / "tiny_bundle"


def test_load_bundle_builds_nodes_and_edges():
    graph = load_bundle(FIXTURES / "valid")
    ids = {c["id"] for c in graph.concepts}
    assert ids == {"overview", "services/billing"}
    # overview links to services/billing.md and billing links back
    pairs = {(e["source"], e["target"]) for e in graph.edges}
    assert ("overview", "services/billing") in pairs
    assert ("services/billing", "overview") in pairs


def test_welcome_comes_from_root_index():
    graph = load_bundle(FIXTURES / "valid")
    assert "Tiny Service" in graph.welcome_html


def test_bundle_root_absolute_links_resolve(tmp_path):
    bundle = tmp_path / "b"
    (bundle / "tables").mkdir(parents=True)
    (bundle / "index.md").write_text("# b\n")
    (bundle / "tables" / "orders.md").write_text(
        "---\ntype: Data Model\n---\n\nFK to [customers](/tables/customers.md).\n"
    )
    (bundle / "tables" / "customers.md").write_text("---\ntype: Data Model\n---\n\nCustomers.\n")
    graph = load_bundle(bundle)
    pairs = {(e["source"], e["target"]) for e in graph.edges}
    assert ("tables/orders", "tables/customers") in pairs


def test_external_and_missing_links_are_not_edges(tmp_path):
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "a.md").write_text(
        "---\ntype: Module\n---\n\nSee [docs](https://example.com) and "
        "[ghost](missing.md) and [log](log.md).\n"
    )
    graph = load_bundle(bundle)
    assert graph.edges == []


def test_build_visualization_writes_selfcontained_html():
    out = build_visualization(FIXTURES / "valid", None)
    try:
        html = out.read_text()
        assert out.name == "okf-viewer.html"
        assert "services/billing" in html
        assert "#concept:" in html  # intra-bundle links rewritten for in-app nav
        assert "http://" not in html and "https://cdn" not in html  # no external deps
    finally:
        out.unlink()


def test_build_visualization_rejects_empty_dir(tmp_path):
    with pytest.raises(ValueError, match="nothing to visualize"):
        build_visualization(tmp_path, None)
