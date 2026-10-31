# Publishing PhytoMiner

The package version comes from `phytominer.__version__`. Update that value,
changelog, README, migration notes and versioned validation documents together.
Keep dependency, request and dataset-schema versions independent.

Commit on `main`, push, and wait for the exact commit's Verify workflow to pass
all five jobs: Linux, macOS, Windows, minimum dependencies and performance.
Create `v<version>` on that commit and push the tag. Dispatch the publishing
workflow on the tag:

```bash
gh workflow run publish.yml --ref v0.3.0
```

The workflow checks the package version, tag, checkout SHA and successful CI
jobs, builds and audits the wheel/sdist, checks isolated installation, saves the
exact upload files as an Actions artifact, and publishes using the existing
`PYPI_API_TOKEN` repository secret. The token is available only to the upload
step. Pushes and GitHub release events do not publish automatically.

After success, verify the PyPI version, hashes and installation from the public
index. Create the GitHub release from the same tag and attach the exact files
downloaded from the publishing workflow artifact. Update issue evidence links
when versioned documentation moves. Reconcile release/tag metadata before
creating anything; retain previously published lower-version releases.
