"""Explicit local annotation imports and derived datasets."""

from pathlib import Path
lazy import polars as pl
from .models import ValidationError, AnnotationError
from .storage import checksum
from .inputs import _result_identity
from .lifecycle import _run_lock
from .dataset import DatasetWriter, HomologDataset


def join_annotations(
    dataset: HomologDataset,
    annotation_file: str | Path,
    *,
    organism_column="organism_id",
    gene_column="gene_name",
    has_header=True,
    column_names=None,
    whitespace: str = "reject",
    output_dir: str | Path | None = None,
) -> pl.LazyFrame | HomologDataset:
    """Left join unique organism/gene annotations; ambiguous keys are errors."""
    path = Path(annotation_file)
    if path.suffix == ".parquet":
        annotation = pl.scan_parquet(path)
    elif path.suffix in (".csv", ".tsv"):
        if not has_header and not column_names:
            raise ValidationError("Headerless input requires explicit column_names")
        annotation = pl.scan_csv(
            path,
            separator="\t" if path.suffix == ".tsv" else ",",
            has_header=has_header,
            new_columns=column_names,
            infer_schema=False,
        )
    else:
        raise ValidationError("Annotation format must be CSV, TSV or Parquet")
    keys = ["organism_id", "gene_name"]
    if whitespace not in ("reject", "trim"):
        raise AnnotationError("whitespace must be reject or trim")
    try:
        schema = annotation.collect_schema()
    except (pl.exceptions.PolarsError, OSError) as exc:
        raise AnnotationError(f"Cannot read annotation: {exc}") from exc
    names = schema.names()
    mapping = {organism_column: "organism_id", gene_column: "gene_name"}
    if organism_column == gene_column or not set(mapping) <= set(names):
        raise AnnotationError("Missing annotation key columns or conflicting mappings")
    if len({mapping.get(n, n) for n in names}) != len(names):
        raise AnnotationError("Column mapping collides with existing columns")
    if any(n == "annotation_match" or n.startswith("_") for n in names):
        raise AnnotationError("Reserved annotation column name")
    if any(schema[c] != pl.String for c in mapping):
        raise AnnotationError("Annotation identifier columns must be strings")
    annotation = annotation.rename(mapping)
    if whitespace == "trim":
        annotation = annotation.with_columns(pl.col(keys).str.strip_chars())
    invalid = pl.col(keys).is_null() | (pl.col(keys).str.strip_chars() == "")
    if whitespace == "reject":
        invalid = invalid | (pl.col(keys) != pl.col(keys).str.strip_chars())
    if annotation.filter(pl.any_horizontal(invalid)).limit(1).collect().height:
        raise AnnotationError("Annotation keys must be nonempty and trimmed")
    if (
        annotation.group_by(keys)
        .len()
        .filter(pl.col("len") > 1)
        .limit(1)
        .collect()
        .height
    ):
        raise AnnotationError(
            "Annotation organism/gene keys must be unique after normalization"
        )
    result = (
        dataset.scan("genes")
        .join(
            annotation.with_columns(pl.lit(True).alias("annotation_match")),
            on=keys,
            how="left",
            validate="m:1",
        )
        .with_columns(pl.col("annotation_match").fill_null(False))
    )
    if output_dir is None:
        return result
    root = Path(output_dir)
    if root.resolve() == dataset.root.resolve():
        raise ValidationError("Use a separate output directory for annotated datasets")
    with _run_lock(root):
        writer = DatasetWriter(
            root,
            _result_identity(
                "annotations",
                parent={
                    name: record["sha256"]
                    for name, record in sorted(dataset.manifest["tables"].items())
                    if name not in ("retrieval_events", "relationship_evidence")
                },
                options={
                    "format": path.suffix,
                    "organism_column": organism_column,
                    "gene_column": gene_column,
                    "has_header": has_header,
                    "column_names": column_names,
                    "whitespace": whitespace,
                },
                annotation=checksum(path),
            ),
            kind="annotated",
        )
        for table in dataset.manifest["tables"]:
            writer.write(table, dataset.scan(table))
        writer.write("annotations", annotation)
        writer.write("annotated_genes", result)
        return writer.finish()
