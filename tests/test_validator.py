from pathlib import Path

import pytest

from okapi.validator import validate_bundle

FIXTURES = Path(__file__).parent / "fixtures" / "tiny_bundle"


def test_valid_bundle_passes():
    report = validate_bundle(FIXTURES / "valid")
    assert report.ok, report.errors
    assert report.errors == []
    assert report.warnings == []
    assert report.concept_count == 2  # overview.md + services/billing.md


def test_invalid_bundle_fails():
    report = validate_bundle(FIXTURES / "invalid")
    assert not report.ok


def test_missing_type_is_an_error():
    report = validate_bundle(FIXTURES / "invalid")
    assert any("missing-type.md" in e and "required field 'type'" in e for e in report.errors)


def test_missing_frontmatter_is_an_error():
    report = validate_bundle(FIXTURES / "invalid")
    assert any("no-frontmatter.md" in e and "missing frontmatter" in e for e in report.errors)


def test_concept_content_in_index_is_an_error():
    report = validate_bundle(FIXTURES / "invalid")
    assert any("index.md" in e and "reserved filename" in e for e in report.errors)


def test_unknown_type_and_missing_recommended_fields_warn_not_fail():
    report = validate_bundle(FIXTURES / "invalid")
    assert any("bare.md" in w and "not in the known vocabulary" in w for w in report.warnings)
    assert any("bare.md" in w and "recommended field" in w for w in report.warnings)
    # warnings never appear in errors
    assert not any("bare.md" in e for e in report.errors)


def test_directory_without_index_warns():
    report = validate_bundle(FIXTURES / "invalid")
    assert any(w.startswith("orphans/") and "no index.md" in w for w in report.warnings)


def test_reserved_log_md_without_frontmatter_is_fine():
    report = validate_bundle(FIXTURES / "valid")
    assert not any("log.md" in e for e in report.errors)


def test_unterminated_frontmatter_is_an_error(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "index.md").write_text("# ok\n")
    (bundle / "broken.md").write_text("---\ntype: module\n# no closing delimiter\n")
    report = validate_bundle(bundle)
    assert any("broken.md" in e and "unterminated" in e for e in report.errors)


def test_non_directory_is_an_error(tmp_path):
    report = validate_bundle(tmp_path / "does-not-exist")
    assert not report.ok


def test_empty_directory_is_an_error(tmp_path):
    report = validate_bundle(tmp_path)
    assert not report.ok
    assert any("no markdown files" in e for e in report.errors)
