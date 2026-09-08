"""Unit tests for the NEXRAD station catalog."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from earthlens.radar import Station, StationCatalog
from earthlens.radar import catalog as catalog_mod
from earthlens.radar.catalog import clear_catalog_cache

pytestmark = [pytest.mark.radar, pytest.mark.unit]

_YAML = """
stations:
  KTLX: {name: "Oklahoma City, OK", latitude: 35.3331, longitude: -97.2778, state: OK}
  KFWS: {name: "Dallas/Fort Worth, TX", latitude: 32.5731, longitude: -97.3031, state: TX}
"""


@pytest.fixture(autouse=True)
def _clear():
    """Each test starts and ends with a clean parse cache."""
    clear_catalog_cache()
    yield
    clear_catalog_cache()


class TestStationCatalog:
    """Tests for StationCatalog loading + lookup."""

    def test_bundled_has_ktlx(self):
        """The shipped catalog resolves KTLX with its published location."""
        ktlx = StationCatalog().get_station("KTLX")
        assert ktlx.state == "OK"
        assert round(ktlx.latitude, 2) == 35.33 and round(ktlx.longitude, 2) == -97.28

    def test_load_from_disk(self, tmp_path, monkeypatch):
        """A monkey-patched CATALOG_PATH is parsed into typed rows."""
        p = tmp_path / "stations.yaml"
        p.write_text(_YAML)
        monkeypatch.setattr(catalog_mod, "CATALOG_PATH", p)
        cat = StationCatalog()
        assert set(cat.datasets) == {"KTLX", "KFWS"}

    def test_second_load_hits_cache(self):
        """A second construction reuses the cached parse."""
        first = sorted(StationCatalog().datasets)
        second = sorted(StationCatalog().datasets)
        assert first == second and "KTLX" in first

    def test_unknown_station_did_you_mean(self):
        """An unknown id raises ValueError with a did-you-mean hint."""
        with pytest.raises(ValueError, match="Did you mean 'KTLX'"):
            StationCatalog().get_station("KTLZ")

    def test_in_bbox(self):
        """in_bbox returns the sites inside the box, sorted."""
        hits = StationCatalog().in_bbox(-100, 33, -95, 37)
        assert "KTLX" in hits and hits == sorted(hits)
        assert "KAMX" not in hits  # Miami is well outside

    def test_empty_block_raises(self, tmp_path, monkeypatch):
        """A YAML with no stations: block raises ValueError."""
        p = tmp_path / "stations.yaml"
        p.write_text("stations:\n")
        monkeypatch.setattr(catalog_mod, "CATALOG_PATH", p)
        with pytest.raises(ValueError, match="empty 'stations:'"):
            StationCatalog()

    def test_invalid_row_raises(self, tmp_path, monkeypatch):
        """A station row with a bad field surfaces a validation ValueError."""
        p = tmp_path / "stations.yaml"
        p.write_text("stations:\n  KBAD: {latitude: 999, longitude: 0}\n")
        monkeypatch.setattr(catalog_mod, "CATALOG_PATH", p)
        with pytest.raises(ValueError, match="failed validation"):
            StationCatalog()

    def test_get_catalog_returns_datasets(self):
        """get_catalog returns the same mapping as .datasets."""
        cat = StationCatalog()
        assert cat.get_catalog() is cat.datasets

    def test_missing_file_raises(self, tmp_path):
        """A non-existent catalog path names the provider and the layout."""
        absent = tmp_path / "absent.yaml"
        with pytest.raises(ValueError, match="NEXRAD catalog path"):
            catalog_mod._load_stations(absent)

    def test_explicit_datasets_skip_autoload(self):
        """Supplying datasets= bypasses the bundled-YAML auto-load."""
        custom = {"KXXX": Station(name="X", latitude=10.0, longitude=20.0, state="NA")}
        cat = StationCatalog(datasets=custom)
        assert cat.datasets == custom
        assert cat.get_station("KXXX").latitude == 10.0


class TestStation:
    """Tests for the Station row model."""

    def test_extra_forbidden(self):
        """An unexpected field is rejected."""
        with pytest.raises(ValidationError):
            Station(latitude=0, longitude=0, bogus=1)

    def test_latitude_range_enforced(self):
        """An out-of-range latitude is rejected."""
        with pytest.raises(ValidationError):
            Station(latitude=999, longitude=0)


class TestStationIdentity:
    """Tests for the site id the loader copies onto each station."""

    def test_code_carries_the_site_id(self):
        """The station is addressed by its ICAO id, which is not in the row body."""
        catalog = StationCatalog()
        for site_id, station in catalog.datasets.items():
            assert station.code == site_id, (
                f"{site_id} row carries code={station.code!r}"
            )

    def test_summary_leads_with_the_code(self):
        """`Station(Aberdeen, SD)` would omit the one field a caller looks up by."""
        station = StationCatalog().datasets["KABR"]
        assert str(station).startswith("Station(KABR,"), str(station)

    def test_a_body_contradicting_the_key_is_rejected(self, tmp_path, monkeypatch):
        """A row filed under one id may not claim another; it would misname itself."""
        path = tmp_path / "stations.yaml"
        path.write_text(
            "stations:\n"
            "  KTLX:\n"
            "    code: KOUN\n"
            "    name: Norman\n"
            "    latitude: 35.2\n"
            "    longitude: -97.4\n"
        )
        monkeypatch.setattr(catalog_mod, "CATALOG_PATH", path)
        with pytest.raises(ValueError, match="does not match the key"):
            StationCatalog()

    def test_a_body_repeating_the_key_is_accepted(self, tmp_path, monkeypatch):
        """Restating the key is redundant, not wrong."""
        path = tmp_path / "stations.yaml"
        path.write_text(
            "stations:\n"
            "  KTLX:\n"
            "    code: KTLX\n"
            "    name: Norman\n"
            "    latitude: 35.2\n"
            "    longitude: -97.4\n"
        )
        monkeypatch.setattr(catalog_mod, "CATALOG_PATH", path)
        assert StationCatalog().datasets["KTLX"].code == "KTLX"

    def test_the_key_is_injected_when_the_body_omits_it(self, tmp_path, monkeypatch):
        """The same loader path, with nothing in the body to override the key."""
        path = tmp_path / "stations.yaml"
        path.write_text(
            "stations:\n"
            "  KTLX:\n"
            "    name: Norman\n"
            "    latitude: 35.2\n"
            "    longitude: -97.4\n"
        )
        monkeypatch.setattr(catalog_mod, "CATALOG_PATH", path)
        assert StationCatalog().datasets["KTLX"].code == "KTLX"

    def test_the_injected_code_stays_out_of_the_serialised_row(self):
        """It mirrors the key, so dumping it would repeat `dataset_id` and widen the YAML."""
        station = StationCatalog().datasets["KTLX"]
        assert "code" not in station.model_dump()
        assert station.code == "KTLX"
        assert "code:" not in str(StationCatalog())

    def test_the_injected_code_participates_in_equality(self):
        """`frozen=True` makes the new field part of `__eq__`, so record it."""
        catalogued = StationCatalog().datasets["KTLX"]
        without_code = Station(**catalogued.model_dump())
        assert without_code != catalogued
        assert Station(code="KTLX", **catalogued.model_dump()) == catalogued
        assert hash(without_code) != hash(catalogued)
