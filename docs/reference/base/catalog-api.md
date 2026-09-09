# Catalog & utility API

The shared plumbing every provider backend builds on: catalog loading, the strict YAML parser, the provider
registry, and the small filesystem helpers. See [Base contracts](contracts.md) for the rules these implement.

## Catalog loading

All 48 catalog loaders route through `load_catalog`, which owns the catalog glob, the `(path, mtime_ns)` cache
key, and the cache registry.

::: earthlens.base.load_catalog

## Strict YAML

The duplicate-key-rejecting loader every catalog parses through — a mapping that declares the same key twice
raises `ValueError` rather than silently keeping the last value.

::: earthlens.base.yaml_loader.load_yaml_strict

## Provider registry

Backends that populate the base `providers` field load it from a per-backend `providers.yaml`.

::: earthlens.base.Provider

::: earthlens.base.load_providers

## Filesystem helpers

::: earthlens.base.safe_filename

## Catalog row summaries

Catalog rows print as one readable line — what the row is called, what units it is in, and how big or how
recent it is — instead of pydantic's field-complete dump. A row opts in by inheriting `SummarisedLeaf` and
declaring the fields worth showing:

```python
from pydantic import Field

from earthlens.base import SummarisedLeaf


class Dataset(SummarisedLeaf):
    _summary_fields = ("id", "title", "bands")

    id: str
    title: str | None = None
    bands: dict[str, int] = Field(default_factory=dict)
```

`print(row)` then gives `Dataset(A/B, A title, 3 bands)`. `None`, empty strings and empty collections are
skipped so a sparse row stays short; a non-empty collection renders as a count, and a `True` boolean renders as
its own field name rather than a bare `True`. Only `__str__` is defined — `__repr__` keeps pydantic's
field-complete form, which is the debugging contract.

Over-long values are clipped to `MAX_FRAGMENT` characters, and the joined summary to `MAX_SUMMARY`. Where the cut
falls depends on what the value reads as: an identifier (`S2A_MSIL2A_20230101T…_T31UFT`) is cut in the middle so
the trailing segment that distinguishes it survives, while prose keeps three quarters of its head and a quarter of
its tail, because a title's first words are what identify it. The summary itself is cut on a fragment boundary —
it drops whole fragments and appends `...` rather than truncating one mid-word.

Declare `_summary_fields` bare, or as an explicit `ClassVar`. Annotating it without `ClassVar` makes pydantic
capture it as a private attribute, which is rejected at class creation rather than silently degrading the
summary to `ClassName()`.

A row needing a shape the declared fields cannot express — a composed `a -> b` identity, a value with a unit,
or anything derived from a property — overrides `summary_parts` and calls `super()`. `_summary_fields` is read
from the class it is declared on, so a subclass that declares its own **replaces** the parent's list rather than
extending it; spell out the inherited names too when both are wanted.

::: earthlens.base.SummarisedLeaf

::: earthlens.base.FluxableLeaf

::: earthlens.base.render_fragment

::: earthlens.base.render_measure

## Catalog keys on rows

Some rows are addressed only by the key they are filed under — a radar station by its ICAO id, an Argo family by
its name — and carry no copy of it. The loader injects the key so the row is self-describing, through one shared
helper rather than a per-loader merge. The key is authoritative: a body may repeat the field, but a body
declaring a different value is rejected with a `ValueError` naming the catalog file, the row and both values. The
injected field is declared `Field(default="", exclude=True)`, so `model_dump()` does not repeat the row's own key.

::: earthlens.base.catalog_source.row_fields_with_key
