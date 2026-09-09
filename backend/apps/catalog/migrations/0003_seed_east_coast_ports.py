"""Seed the East Coast India ports required by the project.

Idempotent forward: uses update_or_create keyed on (name, country).
Reverse: removes the seeded ports by name.
"""
from django.db import migrations

# name, country, coast, latitude, longitude, port_type, unlocode
EAST_COAST_PORTS = [
    ("Paradip", "India", "east_coast_india", "20.264000", "86.670000", "seaport", "INPRT"),
    ("Visakhapatnam", "India", "east_coast_india", "17.686000", "83.218000", "seaport", "INVTZ"),
    ("Gangavaram", "India", "east_coast_india", "17.630000", "83.230000", "terminal", ""),
    ("Gopalpur", "India", "east_coast_india", "19.290000", "84.960000", "seaport", ""),
    ("Dhamra", "India", "east_coast_india", "20.780000", "86.980000", "terminal", ""),
    ("Sagar/Sandheads", "India", "east_coast_india", "21.650000", "88.050000", "anchorage", ""),
    ("Haldia", "India", "east_coast_india", "22.030000", "88.060000", "river", "INHAL"),
]


def seed_ports(apps, schema_editor):
    Port = apps.get_model("catalog", "Port")
    for name, country, coast, lat, lon, port_type, unlocode in EAST_COAST_PORTS:
        Port.objects.update_or_create(
            name=name,
            country=country,
            defaults={
                "coast": coast,
                "latitude": lat,
                "longitude": lon,
                "port_type": port_type,
                "unlocode": unlocode,
            },
        )


def unseed_ports(apps, schema_editor):
    Port = apps.get_model("catalog", "Port")
    names = [p[0] for p in EAST_COAST_PORTS]
    Port.objects.filter(name__in=names, country="India").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0002_port_coast_port_port_coast_idx"),
    ]

    operations = [
        migrations.RunPython(seed_ports, unseed_ports),
    ]
