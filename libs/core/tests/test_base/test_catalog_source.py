"""Tests for `earthlens.base.catalog_source` — the shared catalog-loading helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from earthlens.base.catalog_source import row_fields_with_key


class TestRowFieldsWithKey:
    """Tests for the key-injection rule the four injecting loaders share."""

    def test_the_key_is_copied_onto_a_body_that_omits_it(self) -> None:
        """A row addressed only by its mapping key cannot otherwise name itself."""
        assert row_fields_with_key({"name": "Norman"}, "code", "KTLX") == {
            "name": "Norman",
            "code": "KTLX",
        }

    def test_a_body_repeating_the_key_is_accepted(self) -> None:
        """Restating the key is redundant, not wrong."""
        assert row_fields_with_key({"code": "KTLX"}, "code", "KTLX") == {"code": "KTLX"}

    def test_a_body_contradicting_the_key_is_rejected(self) -> None:
        """A row that claimed another key would misname how it is addressed."""
        with pytest.raises(ValueError, match="does not match the key"):
            row_fields_with_key({"code": "KOUN"}, "code", "KTLX")

    def test_the_error_names_the_row_the_field_and_both_values(self) -> None:
        """The message has to be actionable from the catalog file alone."""
        with pytest.raises(ValueError) as excinfo:
            row_fields_with_key({"code": "KOUN"}, "code", "KTLX", noun="station")
        message = str(excinfo.value)
        assert "station" in message
        assert "'KTLX'" in message and "'KOUN'" in message
        assert "code=" in message

    @pytest.mark.parametrize("body", [None, {}], ids=["none", "empty"])
    def test_an_empty_body_still_gets_the_key(self, body) -> None:
        """A row with no fields of its own is the case the injection exists for."""
        assert row_fields_with_key(body, "name", "phy") == {"name": "phy"}

    def test_the_body_is_not_mutated(self) -> None:
        """The parse cache shares row bodies, so writing through would leak."""
        body = {"name": "Norman"}
        row_fields_with_key(body, "code", "KTLX")
        assert body == {"name": "Norman"}

    def test_other_fields_are_carried_through_unchanged(self) -> None:
        """Injection adds one field; it does not filter the rest."""
        fields = row_fields_with_key(
            {"name": "Norman", "latitude": 35.2}, "code", "KTLX"
        )
        assert fields["name"] == "Norman" and fields["latitude"] == 35.2

    def test_the_default_noun_is_used_when_none_is_given(self) -> None:
        """A caller that does not name its row kind still gets a readable error."""
        with pytest.raises(ValueError, match="row 'phy'"):
            row_fields_with_key({"name": "bgc"}, "name", "phy")

    def test_the_error_names_the_catalog_file_when_one_is_given(self) -> None:
        """Four loaders share this message; only the path says which YAML to open."""
        with pytest.raises(ValueError) as excinfo:
            row_fields_with_key(
                {"code": "KOUN"},
                "code",
                "KTLX",
                noun="station",
                source=Path("radar_data_catalog.yaml"),
            )
        assert str(excinfo.value).startswith("radar_data_catalog.yaml station 'KTLX'")

    def test_the_error_omits_the_prefix_when_no_source_is_given(self) -> None:
        """A caller with no path in hand must not produce a 'None row' message."""
        with pytest.raises(ValueError) as excinfo:
            row_fields_with_key({"code": "KOUN"}, "code", "KTLX")
        assert str(excinfo.value).startswith("row 'KTLX'")

    def test_a_falsy_declared_value_still_counts_as_a_mismatch(self) -> None:
        """An empty string is a declared value, not an absent one."""
        with pytest.raises(ValueError, match="does not match the key"):
            row_fields_with_key({"level": ""}, "level", "country")
