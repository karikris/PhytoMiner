# PhytoMiner BioMart rewrite review

Review date: 2026-04-18.

Repository reviewed: `https://github.com/karikris/PhytoMiner`, cloned to `/home/toffe/PhytoMiner`.

## Service reality

The package is currently built around the old PhytoMine/InterMine API:

- `https://phytozome-next.jgi.doe.gov/phytomine/service/version/ws`
- `https://phytozome-next.jgi.doe.gov/phytomine/service/model`

Both now return `410 Gone` from the current Phytozome host.

The active service surface is BioMart:

- `https://phytozome-next.jgi.doe.gov/biomart/martservice?type=registry`
- `https://phytozome-next.jgi.doe.gov/biomart/martservice?type=datasets&mart=phytozome_mart`
- `https://phytozome-next.jgi.doe.gov/biomart/martservice?type=attributes&dataset=phytozome`
- `https://phytozome-next.jgi.doe.gov/biomart/martservice?type=filters&dataset=phytozome`

The registry advertises `phytozome_mart`, `phytozome_diversity_mart`, `sequence_mart`, archive marts, and `serverVirtualSchema="zome_mart"`. The current `phytozome_mart` datasets include `phytozome`, `phytozome_clusters`, and several pan-genome cluster datasets. `phytozome` was reported by the dataset endpoint as `Phytozome V14 Genomes` with a `2026-03-12 10:52:22` timestamp.

A simple XML BioMart query against `gene_name_filter=AT1G01090` works and returns current rows:

```text
Organism Name        Gene Name   PAC Gene ID   Transcript Name   Peptide Name
Athaliana_TAIR10     AT1G01090   19650207      AT1G01090.1       AT1G01090.1
Athaliana_Araport11  AT1G01090   37392605      AT1G01090.1       AT1G01090.1
```

Important BioMart constraint: attributes from different attribute pages cannot be mixed in one query. A query combining `features` and `orthologs` attributes returned:

```text
Query ERROR: caught BioMart::Exception::Usage: Attributes from multiple attribute pages are not allowed
```

So the rewrite must split feature, ortholog, expression/coexpression, sequence, and cluster retrieval into separate query types and join them locally.

## Current package shape

The package is small:

- `phytominer/api.py`: current external API calls, all InterMine.
- `phytominer/config.py`: service URL, old InterMine view paths, default paths and columns.
- `phytominer/processing.py`: chunking, deduplication, old fetch wrappers, CSV merge helpers.
- `phytominer/workflow.py`: user-facing three-step pipeline and checkpoints.
- `phytominer/data.py`: NDH TSV reader plus unused subcomplex dictionaries.
- `phytominer/utils.py`: logging summary and heatmap helper.
- `tests/`: mostly mocks around existing function names.

## Redundant or obsolete code

| Code | Status | Why | Replacement direction |
| --- | --- | --- | --- |
| `pyproject.toml:21-27` dependency on `intermine` | Remove | Old backend is gone. | Keep `requests` or move to `httpx`; add XML/TSV parsing helpers only if needed. |
| `pyproject.toml:24-26` hard dependency on `seaborn`, `matplotlib` | Move to optional extra or remove | Visualization is not core fetching logic and pulls heavy dependencies. | `phytominer[viz]` extra if heatmap stays. |
| `phytominer/config.py:8-11` `PHYTOZOME_SERVICE_URL` | Replace | Points to `/phytomine/service`, which returns `410 Gone`. | `BIOMART_SERVICE_URL = "https://phytozome-next.jgi.doe.gov/biomart/martservice"` plus mart/dataset config. |
| `phytominer/config.py:35-45` `HOMOLOGS_COLUMN_ORDER`, `HOMOLOGS_QUERY_VIEW` | Remove | InterMine object paths do not apply to BioMart XML attributes. | New BioMart schema constants per attribute page: feature, ortholog, expression, coexpression, sequence, cluster. |
| `phytominer/config.py:46-56` `GENES_QUERY_VIEW` | Remove | InterMine `Gene` view paths and outer joins do not exist in BioMart. | Separate BioMart query specs per page; join locally by gene/transcript IDs. |
| `phytominer/config.py:14` `DEFAULT_SLEEP` | Remove or wire in | Currently unused. | Use retry/backoff config in the BioMart client if needed. |
| `phytominer/config.py:30-32` old `primaryIdentifier`/`organism.shortName` join constants | Replace | These names are InterMine-shaped. | Use normalized internal columns such as `gene_name`, `organism_name`, `organism_id`, `transcript_name`, `pac_gene_id`. |
| Entire `phytominer/api.py` | Rewrite | Imports `intermine.webservice.Service`, uses `new_query("Homolog")`, `new_query("Gene")`, `add_view`, `outerjoin`, and InterMine constraints. | New `BioMartClient` plus functions like `fetch_gene_features`, `fetch_orthologs`, `fetch_expression`, `fetch_sequences`, `fetch_clusters`. |
| `phytominer/api.py:36-42` Homolog query construction | Remove | BioMart does not have this InterMine `Homolog` model/query API. | XML query against `dataset="phytozome"` ortholog page attributes. |
| `phytominer/api.py:49-63` Homolog row mapping | Replace | Source keys like `ortholog_gene.primaryIdentifier` and `ortholog_organism.shortName` are InterMine keys. | Normalize BioMart fields: `ortholog__dm_gene_name`, `ortholog__dm_organism_name`, `ortholog__dm_ortholog_gene_name`, `ortholog__dm_ortholog_organism_name`, `ortholog__dm_relationship`, `ortholog_group`. |
| `phytominer/api.py:101-109` Gene query and outer joins | Remove | BioMart blocks cross-page attributes and has no InterMine outer joins. | Run independent BioMart queries for features, expression, coexpression, sequences, then join. |
| `phytominer/processing.py:86-108` `initial_fetch` | Rewrite | Wrapper around old `phytozome_homologs` and old column assumptions. | New entry point should resolve source gene list, query orthologs/groups, normalize, and apply target filters. |
| `phytominer/processing.py:110-134` `subsequent_fetch` | Likely remove | Iterative pairwise traversal was a workaround for the old API. BioMart exposes ortholog groups and cluster datasets directly. | Prefer one ortholog-group or cluster expansion pass, then local filtering by target organisms. Keep only if scientific workflow explicitly still needs transitive search. |
| `phytominer/processing.py:59-84` `process_homolog_data` | Partially keep | Dedup/ranking idea may remain, but it assumes InterMine column names and relationship categories. | Rewrite for normalized BioMart columns; preserve relationship ranking if BioMart relationship values match. |
| `phytominer/processing.py:16-57` `parallel_chunk_fetch` | Keep after cleanup | Generic I/O chunk executor is useful. | Rename to backend-neutral helper; add rate limiting, deterministic order if needed, and explicit error policy. |
| `phytominer/processing.py:136-151` `step2_merge` | Keep if local TSV validation remains | Generic pandas merge. | Rename columns to new normalized schema. |
| `phytominer/processing.py:153-166` `load_master_df` | Adapt | Validates old columns and returns `None` silently. | Validate new schema and raise/return typed validation errors. |
| `phytominer/processing.py:168-183` `genes_fetch` | Rewrite | Calls old `phytozome_genes`. | Dispatch to BioMart feature/expression/sequence queries. |
| `phytominer/workflow.py:29-96` `homologs_pipe` | Rewrite | User-facing shape is tied to old "initial organism + subsequent organisms" traversal and InterMine column names. | Preserve name as compatibility facade if useful, but implement new BioMart workflow. |
| `phytominer/workflow.py:124-177` `genes_pipe` | Rewrite | Fetches InterMine gene details by `primaryIdentifier`. | New detail workflow should explicitly request feature, expression, coexpression, and/or sequence pages. |
| `phytominer/workflow.py:98-122` `join_tsvs` | Mostly keep | Independent of InterMine. | Update expected ID column to normalized `gene_name` or configurable join key. |
| `phytominer/workflow.py:92-94` automatic heatmap generation | Remove from core pipeline | Fetching should not force visualization side effects. | Make visualization explicit/optional. |
| `phytominer/data.py:8-28` `SUBCOMPLEX_DICT`, `SUBUNIT_TO_SUBCOMPLEX` | Currently dead code | Not imported or used by workflows/tests. | Move into a curated domain-data module only if the rewrite actually uses it. |
| `phytominer/data.py:4` `TSV_DIR` import | Remove | Imported but unused. | None. |
| `phytominer/data.py:30-97` `read_tsv_files` | Conditional keep | Useful only for the local `ndh*.tsv` validation workflow. | Generalize file pattern/header handling and join key. |
| `phytominer/utils.py:10-46` `pivotmap` | Move to optional or fix | Not core; path handling appears wrong because `HEATMAP_DIR` is a directory but passed to `savefig`. | Optional `viz.py`; require output file path. |
| `phytominer/utils.py:77-81` `log_message` | Remove | Trivial wrapper around `logger.info`; unused. | None. |
| `README.md` | Rewrite | Documents InterMine as the backend and the old pipeline. | New BioMart XML examples and updated workflow/API. |
| `tests/test_processing.py` and `tests/test_workflows.py` | Rewrite mostly from scratch | Tests mock the old backend and function signatures. | Add BioMart XML builder tests, TSV parser tests, normalization tests, and optional live integration tests. |

## Code worth preserving

Some ideas are still useful but should be separated from the old backend:

- Chunking/concurrency from `parallel_chunk_fetch`, after adding rate limiting and a clearer error policy.
- Checkpointing from `workflow.py`, after making checkpoint names input-hash based and backend neutral.
- Local TSV merge support if the NDH/subunit validation step is still part of the scientific workflow.
- Deduplication/ranking by relationship if BioMart relationship semantics are confirmed equivalent.
- `log_summary`, although it should not assume old column names.

## New BioMart data model

Use a normalized internal schema and treat BioMart attribute names as adapter details.

Suggested core columns:

- `source_gene_name`
- `source_organism_name`
- `source_organism_id`
- `ortholog_gene_name`
- `ortholog_organism_name`
- `ortholog_organism_id`
- `ortholog_group`
- `relationship`
- `pac_gene_id`
- `transcript_name`
- `pac_transcript_id`
- `peptide_name`
- `subunit`

Do not carry forward InterMine-shaped names like:

- `primaryIdentifier`
- `secondaryIdentifier`
- `organism.shortName`
- `organism.proteomeId`
- `gene.genomicOrder`
- `sequence.residues`
- `CDSs.gene.CDSs.name`

If backward compatibility is needed, provide an explicit `to_legacy_columns()` adapter rather than making old names the new internal schema.

## BioMart query design

Create a small backend layer, for example:

- `phytominer/biomart/client.py`
- `phytominer/biomart/xml.py`
- `phytominer/biomart/schemas.py`
- `phytominer/biomart/normalize.py`

Client responsibilities:

- Build XML with `xml.etree.ElementTree`, not string concatenation.
- Submit to `/biomart/martservice` with `query=<XML>`.
- Expose metadata helpers for `registry`, `datasets`, `attributes`, `filters`.
- Parse TSV, CSV, and FASTA outputs deterministically.
- Use timeouts, retry/backoff, and meaningful exceptions.
- Cache metadata, because attribute/filter names are service data.

Core query functions:

- `fetch_gene_features(gene_names, attributes=...)`
- `fetch_orthologs(gene_names, target_organisms=None)`
- `fetch_expression(gene_names, sample_groups=None)`
- `fetch_coexpression(gene_names, sample_groups=None)`
- `fetch_sequences(gene_names, sequence_type="peptide_sequence" | "coding" | "cdna")`
- `fetch_clusters(transcript_ids=None, cluster_ids=None, node=None)`

Current metadata confirms these useful `phytozome` fields:

- Feature filters: `gene_name_filter`, `transcript_name_filter`, `peptide_name_filter`, `pac_gene_id`, `pac_transcript_id`, `organism_id`.
- Feature attributes: `organism_name`, `organism_id`, `organism_tla`, `gene_name1`, `gene_id`, `transcript_name1`, `transcript_id`, `peptide_name`, coordinates, domain annotations.
- Ortholog attributes: `ortholog_group`, `ortholog__dm_gene_name`, `ortholog__dm_organism_name`, `ortholog__dm_ortholog_gene_name`, `ortholog__dm_ortholog_organism_name`, `ortholog__dm_relationship`.
- Expression/coexpression attributes: `expression__dm_*`, `coexpression__dm_*`.
- Cluster dataset: `phytozome_clusters`, with `cluster_id`, `cluster_name`, `cluster_node`, `number_of_members`, organism-specific member attributes, and `transcript_id_list`.

## Proposed rewrite phases

1. Add BioMart metadata and XML client tests using canned responses.
2. Implement XML builder and TSV parser with no workflow changes.
3. Implement `fetch_gene_features` and verify with `AT1G01090`.
4. Implement ortholog query in isolation. This needs performance testing because a naive direct ortholog row query timed out in this review, even though `count=1` returned a count.
5. Normalize output to a backend-neutral schema.
6. Replace `phytozome_homologs` and `phytozome_genes` behind compatibility functions, or remove them in a breaking release.
7. Redesign `homologs_pipe` around ortholog groups/clusters rather than iterative pairwise traversal.
8. Redesign `genes_pipe` as explicit detail enrichment: features, expression, coexpression, sequences.
9. Move visualization and NDH TSV helpers out of the core fetch path.
10. Rewrite README, tests, and dependency metadata.

## Testing notes

`pytest -q` could not run in this environment because pandas failed during import with:

```text
ValueError: numpy.dtype size changed, may indicate binary incompatibility.
Expected 96 from C header, got 88 from PyObject
```

That is an environment ABI issue, not a package test failure. The current tests are still insufficient for the rewrite because they mock old InterMine functions rather than testing request construction, response parsing, and service schema normalization.

## Bottom line

Treat the existing package as a workflow sketch, not as code to incrementally patch. Keep the ideas of chunking, checkpointing, TSV merging, and deduplication. Replace the backend, schemas, user-facing docs, and most tests. The InterMine-specific code is redundant because the service URLs are gone and the query model is incompatible with BioMart XML.
