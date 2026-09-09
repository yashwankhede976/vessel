"""
PostGIS-compatible geospatial field helper.

The platform targets PostgreSQL/PostGIS in production, but must also run on
plain PostgreSQL or SQLite for local development / CI where the native GIS
stack (GDAL/GEOS) may be absent.

Strategy:
- When ``settings.USE_POSTGIS`` is true AND ``django.contrib.gis`` can be
  imported, ``geo_point_field()`` returns a real GeoDjango ``PointField``
  (spatially indexed, stored as PostGIS ``geometry(Point, 4326)``).
- Otherwise it returns ``None`` and models fall back to explicit
  ``latitude``/``longitude`` ``DecimalField`` columns (which work on any
  backend and carry no floating-point rounding error).

Models therefore always expose ``latitude`` / ``longitude`` decimals as the
portable representation, and additionally a ``geom`` point column when PostGIS
is enabled. This keeps a single codebase PostGIS-ready without requiring the
GIS toolchain everywhere.

See docs/ARCHITECTURE.md §7 (PostgreSQL/PostGIS data layer).
"""
from __future__ import annotations

from typing import Optional

from django.conf import settings


def postgis_enabled() -> bool:
    """True only if PostGIS use is requested and the GIS stack is importable."""
    if not getattr(settings, "USE_POSTGIS", False):
        return False
    try:  # pragma: no cover - depends on native libs
        import django.contrib.gis.db.models  # noqa: F401
    except Exception:
        return False
    return True


def geo_point_field(**kwargs) -> Optional[object]:
    """Return a GeoDjango PointField when PostGIS is enabled, else None.

    Callers add the returned field as ``geom`` only when it is not None, and
    always keep the portable latitude/longitude decimals.
    """
    if not postgis_enabled():  # pragma: no cover - branch depends on env
        return None
    from django.contrib.gis.db import models as gis_models

    kwargs.setdefault("srid", 4326)
    kwargs.setdefault("geography", True)
    kwargs.setdefault("null", True)
    kwargs.setdefault("blank", True)
    return gis_models.PointField(**kwargs)
