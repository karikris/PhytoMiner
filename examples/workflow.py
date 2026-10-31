"""Executable live example; tests inject a fixture client instead of networking."""

from pathlib import Path
from phytominer import HomologDataset, Seed, fetch_homologs, join_annotations


def run(output_dir, *, client=None, annotation_file=None):
    dataset = fetch_homologs(
        [Seed("167", "AT1G01090", "NDHA")], output_dir=output_dir, client=client
    )
    counts = dataset.summary().collect()
    with dataset.connect() as connection:
        edge_count = connection.sql("SELECT count(*) FROM relationships").fetchall()[0][
            0
        ]
    if annotation_file is not None:
        annotated = join_annotations(dataset, annotation_file)
        assert not isinstance(annotated, HomologDataset)
        annotated.sink_parquet(Path(output_dir) / "annotated_genes.parquet")
    return dataset, counts, edge_count


if __name__ == "__main__":
    dataset, counts, total = run("phytominer-output")
    print(counts)
    print(
        f"{total} reported relationships; {dataset.manifest['unresolved_identity_rows']} unresolved identities"
    )
