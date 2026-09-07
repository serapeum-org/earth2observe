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
skipped so a sparse row stays short; a non-empty collection renders as a count. Long fragments are
clipped in the middle at `MAX_FRAGMENT` characters and the joined summary at `MAX_SUMMARY`, so a clipped asset
path still shows the last segment that distinguishes it. Only `__str__` is defined —
`__repr__` keeps pydantic's field-complete form, which is the debugging contract.

Declare `_summary_fields` bare, or as an explicit `ClassVar`. Annotating it without `ClassVar` makes pydantic
capture it as a private attribute, which is rejected at class creation rather than silently degrading the
summary to `ClassName()`.

A row needing a shape the declared fields cannot express — a composed `a -> b` identity, a value with a unit,
or anything derived from a property — overrides `summary_parts` and calls `super()`.

::: earthlens.base.SummarisedLeaf

::: earthlens.base.FluxableLeaf

::: earthlens.base.render_fragment
