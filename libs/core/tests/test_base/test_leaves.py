"""Tests for `earthlens.base.leaves` — `SummarisedLeaf` and `FluxableLeaf`."""

from __future__ import annotations

import pytest

from earthlens.base.leaves import FluxableLeaf, SummarisedLeaf, _render


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


class Sized(SummarisedLeaf):
    """A leaf whose declared fields cover the four collection types."""

    _summary_fields = ("tags", "levels", "codes", "frozen")

    tags: list[str] = []
    levels: tuple[int, ...] = ()
    codes: set[str] = set()
    frozen: frozenset[str] = frozenset()


class Numeric(SummarisedLeaf):
    """A leaf whose declared fields are falsy-but-meaningful numbers."""

    _summary_fields = ("count", "ratio", "flag")

    count: int = 0
    ratio: float = 0.0
    flag: bool = False


class Typo(SummarisedLeaf):
    """A leaf declaring a field name it does not actually carry."""

    _summary_fields = ("id", "nonexistent")

    id: str = "A/B"


class Nested(SummarisedLeaf):
    """A leaf whose declared field holds another summarised leaf."""

    _summary_fields = ("id", "inner")

    id: str = "outer"
    inner: Undeclared | None = None


class Var(FluxableLeaf):
    """A flux-aware leaf declaring one field."""

    _summary_fields = ("units",)

    units: str | None = None


class Pairing(Var):
    """A flux-aware leaf that prepends a composed fragment to the summary."""

    def summary_parts(self) -> list[str]:
        """Return an `a -> b` pair ahead of whatever the base contributes."""
        return ["a -> b", *super().summary_parts()]


class TestRender:
    """Tests for the `_render` field-value formatter."""

    def test_none_renders_as_nothing(self):
        """`None` carries no information and is dropped."""
        assert _render(None, "units") == ""

    def test_empty_string_renders_as_nothing(self):
        """An empty string is as absent as `None`."""
        assert _render("", "units") == ""

    def test_whitespace_only_string_renders_as_nothing(self):
        """A blank string collapses to empty rather than a stray gap."""
        assert _render("   ", "units") == ""

    def test_string_is_stripped(self):
        """Surrounding whitespace never reaches the summary."""
        assert _render("  K  ", "units") == "K"

    @pytest.mark.parametrize(
        "value, expected", [(0, "0"), (0.0, "0.0"), (False, "False")]
    )
    def test_falsy_scalars_still_render(self, value, expected):
        """Zero and `False` are real values, unlike `None` — they are kept."""
        assert _render(value, "count") == expected, (
            f"{value!r} should render as {expected!r}"
        )

    @pytest.mark.parametrize(
        "value",
        [{}, [], (), set(), frozenset()],
        ids=["dict", "list", "tuple", "set", "frozenset"],
    )
    def test_empty_collections_render_as_nothing(self, value):
        """An empty collection is omitted rather than shown as a zero count."""
        assert _render(value, "bands") == "", f"{value!r} should render as empty"

    @pytest.mark.parametrize(
        "value",
        [{"a": 1, "b": 2}, ["a", "b"], ("a", "b"), {"a", "b"}, frozenset({"a", "b"})],
        ids=["dict", "list", "tuple", "set", "frozenset"],
    )
    def test_non_empty_collections_render_as_a_labelled_count(self, value):
        """Every collection type shows its size against the field's name."""
        assert _render(value, "bands") == "2 bands", (
            f"{value!r} should render as a count"
        )

    def test_the_count_is_labelled_with_the_field_name(self):
        """The label comes from the field, so the count reads as prose."""
        assert _render([1, 2, 3], "levels") == "3 levels"


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

    def test_it_is_a_summarised_leaf(self):
        """The flux mixin builds on the summary base rather than replacing it."""
        assert issubclass(FluxableLeaf, SummarisedLeaf)


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
        """An empty collection is omitted rather than shown as a zero count."""
        assert "bands" not in str(Row(id="A/B", bands={}))

    def test_every_collection_type_is_counted(self):
        """Lists, tuples, sets and frozensets all render as counts."""
        row = Sized(
            tags=["a"], levels=(1, 2), codes={"x"}, frozen=frozenset({"y", "z"})
        )
        assert str(row) == "Sized(1 tags, 2 levels, 1 codes, 2 frozen)"

    def test_falsy_numbers_are_kept(self):
        """A zero count is a fact; only `None` and emptiness are dropped."""
        assert str(Numeric()) == "Numeric(0, 0.0, False)"

    def test_undeclared_leaf_prints_only_its_name(self):
        """A row declaring no fields says so honestly rather than guessing."""
        assert str(Undeclared()) == "Undeclared()"

    def test_a_field_the_row_does_not_carry_is_skipped(self):
        """A declared name with no matching field degrades quietly, not loudly."""
        assert str(Typo()) == "Typo(A/B)"

    def test_a_nested_leaf_renders_through_its_own_str(self):
        """Composition works: the inner leaf formats itself."""
        assert str(Nested(inner=Undeclared())) == "Nested(outer, Undeclared())"

    def test_the_summary_is_a_single_line(self):
        """A row summary never wraps, so it stays greppable in a log."""
        assert "\n" not in str(Row(id="A/B", title="A title", bands={"b": 1}))

    def test_a_subclass_uses_its_own_name(self):
        """The class name is read off the instance, not the declaring base."""
        assert str(Pairing(units="K")).startswith("Pairing(")

    def test_repr_is_left_alone(self):
        """`__repr__` keeps pydantic's field-complete form — the debugging contract."""
        row = Row(id="A/B")
        assert repr(row).startswith("Row(id='A/B'")
        assert "title=None" in repr(row)
        assert repr(row) != str(row)

    def test_str_is_ascii_only(self):
        """The summary survives a `cp1252` console, which an arrow glyph would not."""
        rendered = str(Row(id="A/B", title="A title"))
        assert rendered.encode("cp1252").decode("cp1252") == rendered

    def test_summary_fields_is_not_a_model_field(self):
        """The declaration is class config, so it never becomes data."""
        assert "_summary_fields" not in Row.model_fields

    def test_summary_parts_returns_one_fragment_per_populated_field(self):
        """`summary_parts` is the seam subclasses compose with."""
        assert Row(id="A/B", provider="esa").summary_parts() == ["A/B", "esa"]


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

    def test_the_marker_survives_an_empty_declaration(self):
        """A flux row with nothing else to say still reports its kind."""
        assert str(FluxableLeaf(types="flux")) == "FluxableLeaf(flux)"

    def test_subclass_can_prepend_and_keep_the_marker(self):
        """Overriding `summary_parts` composes with the base via `super()`."""
        assert str(Pairing(units="K")) == "Pairing(a -> b, K, state)"
