"""Tests for `earthlens.base.leaves` — `SummarisedLeaf` and `FluxableLeaf`."""

from __future__ import annotations

import pytest

from earthlens.base.leaves import FluxableLeaf, SummarisedLeaf


class Row(SummarisedLeaf):
    """A leaf declaring a summary, used across the tests below."""

    _summary_fields = ("id", "title", "provider", "bands")

    id: str = ""
    title: str | None = None
    provider: str | None = None
    bands: dict[str, int] = {}


class Undeclared(SummarisedLeaf):
    """A leaf that declares no summary fields."""

    id: str = "x"


class Var(FluxableLeaf):
    """A flux-aware leaf declaring one field."""

    _summary_fields = ("units",)

    units: str | None = None


class TestFluxableLeaf:
    """Tests for the `FluxableLeaf` mixin."""

    def test_default_types_is_none(self):
        """`types` defaults to `None` for state / instantaneous quantities."""
        leaf = FluxableLeaf()
        assert leaf.types is None
        assert leaf.is_flux is False

    def test_types_flux_marks_is_flux_true(self):
        """`types="flux"` flips `is_flux` to `True`."""
        assert FluxableLeaf(types="flux").is_flux is True

    @pytest.mark.parametrize("types", ["state", "instant", "accumulated", "FLUX"])
    def test_non_flux_string_keeps_is_flux_false(self, types):
        """Anything other than the exact string `"flux"` leaves `is_flux` False."""
        assert FluxableLeaf(types=types).is_flux is False

    def test_frozen_model_rejects_mutation(self):
        """The leaf is a frozen pydantic model — assignment raises."""
        leaf = FluxableLeaf(types="flux")
        with pytest.raises(Exception):
            leaf.types = "state"

    def test_extra_fields_rejected(self):
        """`extra="forbid"` blocks unknown fields at construction."""
        with pytest.raises(Exception):
            FluxableLeaf(types="flux", surprise=1)


class TestSummarisedLeafStr:
    """Tests for the one-line `__str__` on `SummarisedLeaf`."""

    def test_declared_fields_render_in_order(self):
        """Fields appear in the order they were declared, not model order."""
        row = Row(id="A/B", title="A title", provider="esa")
        assert str(row) == "Row(A/B, A title, esa)"

    def test_none_and_empty_are_skipped(self):
        """A sparse row stays short instead of printing `None` placeholders."""
        assert str(Row(id="A/B")) == "Row(A/B)"

    def test_empty_string_is_skipped(self):
        """An empty string carries nothing and is dropped like `None`."""
        assert str(Row(id="A/B", title="")) == "Row(A/B)"

    def test_collection_renders_as_a_labelled_count(self):
        """A non-empty collection shows its size, not its contents."""
        row = Row(id="A/B", bands={"b1": 1, "b2": 2, "b3": 3})
        assert str(row) == "Row(A/B, 3 bands)"

    def test_empty_collection_is_skipped(self):
        """An empty collection is omitted rather than shown as `0 bands`."""
        assert "bands" not in str(Row(id="A/B", bands={}))

    def test_undeclared_leaf_prints_only_its_name(self):
        """A row declaring no fields says so honestly rather than guessing."""
        assert str(Undeclared()) == "Undeclared()"

    def test_repr_is_left_alone(self):
        """`__repr__` keeps pydantic's field-complete form — the debugging contract."""
        row = Row(id="A/B")
        assert repr(row).startswith("Row(id='A/B'")
        assert "title=None" in repr(row)
        assert repr(row) != str(row)

    def test_str_is_ascii_only(self):
        """The summary survives a `cp1252` console, which a `→` would not."""
        rendered = str(Row(id="A/B", title="A title"))
        assert rendered.encode("cp1252").decode("cp1252") == rendered

    def test_summary_fields_is_not_a_model_field(self):
        """The declaration is class config, so it never becomes data."""
        assert "_summary_fields" not in Row.model_fields


class TestFluxableLeafStr:
    """Tests for the flux marker `FluxableLeaf` adds to the summary."""

    def test_state_row_is_marked_state(self):
        """A non-flux row ends with `state`."""
        assert str(Var(units="K")) == "Var(K, state)"

    def test_flux_row_is_marked_flux(self):
        """A flux row ends with `flux`."""
        assert str(Var(units="mm", types="flux")) == "Var(mm, flux)"

    def test_is_flux_reaches_str_though_it_is_not_a_field(self):
        """The property is added explicitly; nothing field-driven would find it."""
        row = Var(units="mm", types="flux")
        assert "is_flux" not in row.model_dump()
        assert "flux" in str(row)

    def test_marker_follows_the_declared_fields(self):
        """The flux marker is appended, so declared fields keep their order."""
        assert str(Var(units="K")).index("K") < str(Var(units="K")).index("state")

    def test_subclass_can_prepend_and_keep_the_marker(self):
        """Overriding `summary_parts` composes with the base via `super()`."""

        class Pairing(Var):
            def summary_parts(self) -> list[str]:
                return ["a -> b", *super().summary_parts()]

        assert str(Pairing(units="K")) == "Pairing(a -> b, K, state)"
