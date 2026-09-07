"""Tiny shared base classes for per-variable / per-band catalog rows.

Only carries the slivers of behavior that genuinely repeat across
backends — most leaf metadata is domain-specific (optical bands carry
`wavelength` / `scale` / `offset`; CDS variables carry
`cds_variable` / `cds_pressure_level`; CHIRPS variables carry
`description` / `units`).
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

#: Collection types rendered as a count (`12 bands`) rather than dumped in full.
_SIZED = (dict, list, tuple, set, frozenset)


def _render(value: Any, field: str) -> str:
    """Render one field value for a one-line summary, or `""` to omit it.

    Args:
        value: The attribute's value.
        field: The attribute's name, used to label a collection's count.

    Returns:
        str: The rendered fragment, or `""` when the value carries nothing
        worth showing (`None`, an empty string, or an empty collection).

    Examples:
        - A scalar renders as its stripped text:
            ```python
            >>> _render("  K  ", "units")
            'K'

            ```
        - A collection renders as a count labelled with the field:
            ```python
            >>> _render({"b1": 1, "b2": 2}, "bands")
            '2 bands'

            ```
        - Nothing worth showing renders as the empty string:
            ```python
            >>> [_render(v, "units") for v in (None, "", [])]
            ['', '', '']

            ```
        - Zero is a real value, so it survives:
            ```python
            >>> _render(0, "count")
            '0'

            ```
    """
    if value is None:
        return ""
    if isinstance(value, _SIZED):
        return f"{len(value)} {field}" if value else ""
    text = str(value).strip()
    return text


class SummarisedLeaf(BaseModel):
    """Catalog row that prints as one readable line instead of a field dump.

    A catalog row is normally read for three things — what it is called,
    what units it is in, and how big or how recent it is. Pydantic's default
    `__str__` answers none of them quickly: it prints every field, including
    the `None`s, which is why examples across the docs re-implement the same
    hand-rolled `print(f"...: {row.field}")` blocks.

    `None`, empty strings and empty collections are skipped, so a sparse row
    stays short; a non-empty collection renders as a count (`12 bands`).
    A subclass needing a different shape overrides :meth:`summary_parts`.

    Only `__str__` is defined. `__repr__` is deliberately left as pydantic's
    field-complete form: that is the debugging contract, and doctests and log
    lines can depend on its exact text.

    Examples:
        - Declare the fields worth showing, in order, then print a row:
            ```python
            >>> class Dataset(SummarisedLeaf):
            ...     _summary_fields = ("id", "title", "bands")
            ...     id: str
            ...     title: str | None = None
            ...     bands: dict[str, int] = {}
            >>> print(Dataset(id="A/B", title="A title", bands={"b1": 1}))
            Dataset(A/B, A title, 1 bands)

            ```
        - A sparse row stays short instead of printing `None` placeholders:
            ```python
            >>> class Dataset(SummarisedLeaf):
            ...     _summary_fields = ("id", "title")
            ...     id: str
            ...     title: str | None = None
            >>> print(Dataset(id="A/B"))
            Dataset(A/B)

            ```
        - `__repr__` still carries every field, so debugging is unaffected:
            ```python
            >>> class Dataset(SummarisedLeaf):
            ...     _summary_fields = ("id",)
            ...     id: str
            ...     title: str | None = None
            >>> row = Dataset(id="A/B")
            >>> str(row)
            'Dataset(A/B)'
            >>> repr(row)
            "Dataset(id='A/B', title=None)"

            ```

    See Also:
        FluxableLeaf: Adds a `flux` / `state` marker for variable rows.
    """

    #: Field names to include in `__str__`, in order. Empty means no summary
    #: beyond the class name, which is the honest answer for a row that has
    #: not declared one.
    _summary_fields: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        """Reject a `_summary_fields` spelling pydantic would silently swallow.

        A leading underscore plus a bare annotation — `_summary_fields:
        tuple[str, ...] = (...)` — makes pydantic treat the declaration as a
        private attribute and drop it from the class namespace. Lookup then
        falls through to this base's empty default and the row prints as
        `ClassName()` with no error, no lint warning and no type error. That
        is the one failure this class cannot detect at render time, so it is
        caught at class-creation time instead.

        Args:
            **kwargs: Class-construction keywords, forwarded to the base.

        Raises:
            TypeError: If `_summary_fields` was captured as a private
                attribute, i.e. annotated without `ClassVar`.
        """
        super().__pydantic_init_subclass__(**kwargs)
        if "_summary_fields" in cls.__private_attributes__:
            raise TypeError(
                f"{cls.__name__}._summary_fields is annotated without "
                "ClassVar, so pydantic captured it as a private attribute and "
                "the summary would silently degrade to "
                f"'{cls.__name__}()'. Declare it bare "
                '(`_summary_fields = ("id", ...)`) or as '
                "`ClassVar[tuple[str, ...]]`."
            )

    def summary_parts(self) -> list[str]:
        """Return the rendered fragments that make up the one-line summary.

        Override to prepend a composed fragment (an `a -> b` identity, say)
        or to append a derived one; call `super().summary_parts()` so a base
        class's contribution is kept.

        Returns:
            list[str]: One fragment per declared field that had a value.

        Examples:
            - Only the populated fields produce a fragment:
                ```python
                >>> class Dataset(SummarisedLeaf):
                ...     _summary_fields = ("id", "title", "provider")
                ...     id: str
                ...     title: str | None = None
                ...     provider: str | None = None
                >>> Dataset(id="A/B", provider="esa").summary_parts()
                ['A/B', 'esa']

                ```
            - Prepend a composed fragment by calling `super()`:
                ```python
                >>> class Variable(SummarisedLeaf):
                ...     _summary_fields = ("units",)
                ...     name: str
                ...     nc_name: str
                ...     units: str
                ...     def summary_parts(self) -> list[str]:
                ...         pair = f"{self.name} -> {self.nc_name}"
                ...         return [pair, *super().summary_parts()]
                >>> print(Variable(name="2m_temperature", nc_name="t2m", units="K"))
                Variable(2m_temperature -> t2m, K)

                ```
        """
        parts = []
        for field in self._summary_fields:
            rendered = _render(getattr(self, field, None), field)
            if rendered:
                parts.append(rendered)
        return parts

    def __str__(self) -> str:
        """Return `ClassName(fragment, fragment, ...)` for `print(row)`.

        Returns:
            str: The one-line summary. ASCII only — a `__str__` that raises
            `UnicodeEncodeError` on a `cp1252` console would be worse than a
            plain one.

        Examples:
            - The class names itself, then lists its fragments:
                ```python
                >>> class Band(SummarisedLeaf):
                ...     _summary_fields = ("id", "units")
                ...     id: str
                ...     units: str | None = None
                >>> str(Band(id="B1", units="K"))
                'Band(B1, K)'

                ```
            - A row with nothing to show still names itself honestly:
                ```python
                >>> class Band(SummarisedLeaf):
                ...     id: str = "B1"
                >>> str(Band())
                'Band()'

                ```
        """
        return f"{type(self).__name__}({', '.join(self.summary_parts())})"


class FluxableLeaf(SummarisedLeaf):
    """Catalog row that flags whether its quantity accumulates over time.

    Both ECMWF :class:`earthlens.ecmwf.Variable` and CHIRPS
    :class:`earthlens.chc.Variable` carry an identical `types` field
    plus `is_flux` property — flux quantities (precipitation,
    evapotranspiration, radiation) are accumulated per timestep on
    the server side, so monthly aggregation has to multiply by the
    number of days in the month. State / instantaneous values
    (temperature, pressure) don't need that scaling.

    GEE :class:`earthlens.gee.Band` does NOT inherit from this — its
    raster bands don't carry flux semantics (cloud-screened optical
    reflectance, NDVI, etc.).

    Attributes:
        types: `"flux"` for accumulated quantities, `None` (the
            default) for state / instantaneous values. Concrete
            subclasses may narrow to a `Literal` if they enumerate
            other values.

    Examples:
        - A flux row is marked as such in its summary:
            ```python
            >>> class Variable(FluxableLeaf):
            ...     _summary_fields = ("units",)
            ...     units: str
            >>> print(Variable(units="mm", types="flux"))
            Variable(mm, flux)

            ```
        - Anything that is not exactly `"flux"` reads as state:
            ```python
            >>> class Variable(FluxableLeaf):
            ...     _summary_fields = ("units",)
            ...     units: str
            >>> row = Variable(units="K")
            >>> row.is_flux
            False
            >>> print(row)
            Variable(K, state)

            ```

    See Also:
        SummarisedLeaf: The one-line `__str__` this builds on.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    types: str | None = None

    @property
    def is_flux(self) -> bool:
        """`True` when `types == "flux"`; drives monthly accumulation scaling.

        Returns:
            bool: Whether the quantity accumulates over the timestep.

        Examples:
            - An accumulated quantity is a flux:
                ```python
                >>> FluxableLeaf(types="flux").is_flux
                True

                ```
            - An instantaneous quantity, and the default, are not:
                ```python
                >>> [FluxableLeaf(types=t).is_flux for t in ("state", None)]
                [False, False]

                ```
        """
        return self.types == "flux"

    def summary_parts(self) -> list[str]:
        """Append the `flux` / `state` marker to the declared fields.

        `is_flux` is a property rather than a model field, so nothing
        field-driven picks it up — it has to be added explicitly, and it is
        the single most load-bearing fact about a variable row.

        Returns:
            list[str]: The declared fragments, then `"flux"` or `"state"`.

        Examples:
            - The marker is appended, so declared fields keep their order:
                ```python
                >>> class Variable(FluxableLeaf):
                ...     _summary_fields = ("units",)
                ...     units: str
                >>> Variable(units="mm", types="flux").summary_parts()
                ['mm', 'flux']

                ```
            - A row with no declared fields still reports its kind:
                ```python
                >>> FluxableLeaf().summary_parts()
                ['state']

                ```
        """
        return [*super().summary_parts(), "flux" if self.is_flux else "state"]
