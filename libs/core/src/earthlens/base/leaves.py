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

    Subclasses declare the fields worth showing, in order:

    ```python
    class Dataset(SummarisedLeaf):
        _summary_fields = ("id", "title", "provider")
    ```

    `None`, empty strings and empty collections are skipped, so a sparse row
    stays short; a non-empty collection renders as a count (`12 bands`).
    A subclass needing a different shape overrides :meth:`summary_parts`.

    Only `__str__` is defined. `__repr__` is deliberately left as pydantic's
    field-complete form: that is the debugging contract, and doctests and log
    lines can depend on its exact text.
    """

    #: Field names to include in `__str__`, in order. Empty means no summary
    #: beyond the class name, which is the honest answer for a row that has
    #: not declared one.
    _summary_fields: ClassVar[tuple[str, ...]] = ()

    def summary_parts(self) -> list[str]:
        """Return the rendered fragments that make up the one-line summary.

        Override to prepend a composed fragment (an `a -> b` identity, say)
        or to append a derived one; call `super().summary_parts()` so a base
        class's contribution is kept.

        Returns:
            list[str]: One fragment per declared field that had a value.
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
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    types: str | None = None

    @property
    def is_flux(self) -> bool:
        """`True` when `types == "flux"`; drives monthly accumulation scaling."""
        return self.types == "flux"

    def summary_parts(self) -> list[str]:
        """Append the `flux` / `state` marker to the declared fields.

        `is_flux` is a property rather than a model field, so nothing
        field-driven picks it up — it has to be added explicitly, and it is
        the single most load-bearing fact about a variable row.

        Returns:
            list[str]: The declared fragments, then `"flux"` or `"state"`.
        """
        return [*super().summary_parts(), "flux" if self.is_flux else "state"]
