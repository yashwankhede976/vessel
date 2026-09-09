# Data

Local, versioned datasets and manifests for development and experiments.

**Rules (see [../docs/DEVELOPMENT_WORKFLOW.md](../docs/DEVELOPMENT_WORKFLOW.md) §11):**

- Datasets are versioned and referenced by version, never "latest mutable file".
- Raw and large/processed datasets live in artifact/object storage, **not** in Git — only small, licence-cleared reference data and manifests are committed.
- **Never commit licensed/commercial data** (e.g. Baltic Exchange) or real secrets.
- Each dataset records provenance (source, pull date, access class) — see [../docs/DATA_SOURCES.md](../docs/DATA_SOURCES.md).

Suggested layout:

```
data/
├── raw/          # git-ignored — pulled/imported source data
├── processed/    # git-ignored — engineered/derived datasets
└── manifests/    # committed — version → location + checksum pointers
```

The `raw/` and `processed/` contents are git-ignored (see root `.gitignore`).
