"""Concrete ingestion sources built on the ingestion framework.

Importing this package registers every concrete source class in the registry
(keyed by its `key`), so tasks and the `run_ingestion` management command can
resolve a source by name. Registration is centralized here (rather than a
decorator on each class) so the individual source modules stay import-light and
the full catalogue of sources is visible in one place.

`apps.ingestion.apps.IngestionConfig.ready()` imports this package, so the
registry is populated at app startup.
"""
from __future__ import annotations

from apps.ingestion.registry import register

from .aisstream import AISStreamSource
from .comtrade import ComtradeSource
from .imd import IMDSource
from .incois import INCOISSource
from .india_open_data import (
    CsvDownloadSource,
    DataGovInApiSource,
    MinistryOfCoalSource,
)
from .open_meteo import OpenMeteoSource
from .world_bank import WorldBankSource

# Sources that self-configure (no required constructor arguments) can be run by
# key directly. Config-driven sources (IMD, INCOIS, data.gov.in, CSV downloads)
# require a config object and are invoked programmatically, but are still
# registered so they are discoverable/listable.
SELF_CONFIGURING = {
    "open_meteo",
    "world_bank",
    "un_comtrade",
    "aisstream",  # self-configures from settings, though it is a streaming source
}

_ALL_SOURCES = [
    AISStreamSource,
    ComtradeSource,
    IMDSource,
    INCOISSource,
    DataGovInApiSource,
    CsvDownloadSource,
    MinistryOfCoalSource,
    OpenMeteoSource,
    WorldBankSource,
]


def register_all() -> None:
    """Register every concrete source class (idempotent)."""
    for source_cls in _ALL_SOURCES:
        # register() raises on a duplicate DIFFERENT class; re-registering the
        # same class is a no-op, so this is safe to call more than once.
        try:
            register(source_cls)
        except Exception:  # pragma: no cover - already registered same class
            pass


# Populate the registry on import.
register_all()

__all__ = [
    "AISStreamSource",
    "ComtradeSource",
    "IMDSource",
    "INCOISSource",
    "DataGovInApiSource",
    "CsvDownloadSource",
    "MinistryOfCoalSource",
    "OpenMeteoSource",
    "WorldBankSource",
    "SELF_CONFIGURING",
    "register_all",
]
