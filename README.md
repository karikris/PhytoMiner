# PhytoMiner

Python 3.15+ BioMart XML retrieval and Polars/Parquet/DuckDB analytics.

The 1.0 migration is in progress. See IMPLEMENTATION.md for verified milestones.
The previous backend, pipeline functions, columns, plotting and CSV checkpoints
have been removed. Existing scripts must migrate to the new dataset API.

Install development dependencies with `uv sync --extra dev`; run `uv run pytest`.
