"""Require a matching release tag and successful exact-commit CI before upload."""

import json
import os
import re
import subprocess

EXPECTED_JOBS = {
    "minimum",
    "performance",
    "test (ubuntu-latest)",
    "test (macos-latest)",
    "test (windows-latest)",
}


def gh_json(arguments):
    return json.loads(subprocess.check_output(["gh", *arguments], text=True))


def verify_release(repository, sha, ref, version, query=gh_json):
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Release version must be a stable three-part version")
    if ref != f"refs/tags/v{version}":
        raise ValueError("Dispatch publishing on the tag matching the package version")
    runs = query(
        [
            "run",
            "list",
            "--repo",
            repository,
            "--workflow",
            "verify.yml",
            "--commit",
            sha,
            "--event",
            "push",
            "--status",
            "success",
            "--limit",
            "100",
            "--json",
            "databaseId,headSha,conclusion",
        ]
    )
    for run in runs:
        if run["headSha"] != sha or run["conclusion"] != "success":
            continue
        report = query(
            [
                "run",
                "view",
                str(run["databaseId"]),
                "--repo",
                repository,
                "--json",
                "headSha,status,conclusion,jobs",
            ]
        )
        jobs = report["jobs"]
        if (
            report["headSha"] == sha
            and report["status"] == "completed"
            and report["conclusion"] == "success"
            and {job["name"] for job in jobs} == EXPECTED_JOBS
            and len(jobs) == len(EXPECTED_JOBS)
            and all(
                job["status"] == "completed" and job["conclusion"] == "success"
                for job in jobs
            )
        ):
            return run["databaseId"]
    raise ValueError(
        "No successful exact-commit Verify run with all five required jobs"
    )


def main():
    from phytominer import __version__

    sha = os.environ["GITHUB_SHA"]
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    tag = subprocess.check_output(
        ["git", "rev-parse", f"refs/tags/v{__version__}^{{commit}}"], text=True
    ).strip()
    if head != sha or tag != sha:
        raise ValueError("Checkout, release tag and workflow commit must match")
    run_id = verify_release(
        os.environ["GITHUB_REPOSITORY"], sha, os.environ["GITHUB_REF"], __version__
    )
    print(f"Release {__version__} at {sha} accepted by Verify run {run_id}")


if __name__ == "__main__":
    main()
