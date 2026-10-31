"""Release upload must be gated by the tag and every exact-commit CI job."""

import pytest

from scripts.check_publish import EXPECTED_JOBS, verify_release

SHA = "a" * 40


def evidence():
    return {
        "headSha": SHA,
        "status": "completed",
        "conclusion": "success",
        "jobs": [
            {"name": name, "status": "completed", "conclusion": "success"}
            for name in sorted(EXPECTED_JOBS)
        ],
    }


def query_for(report):
    def query(arguments):
        if arguments[:2] == ["run", "list"]:
            return [{"databaseId": 123, "headSha": SHA, "conclusion": "success"}]
        return report

    return query


def test_accepts_matching_tag_and_all_jobs():
    assert (
        verify_release(
            "owner/repo", SHA, "refs/tags/v0.3.0", "0.3.0", query_for(evidence())
        )
        == 123
    )


@pytest.mark.parametrize("ref", ["refs/heads/main", "refs/tags/v0.2.0"])
def test_rejects_nonmatching_tag(ref):
    with pytest.raises(ValueError, match="tag matching"):
        verify_release("owner/repo", SHA, ref, "0.3.0", query_for(evidence()))


@pytest.mark.parametrize("problem", ["missing_job", "failed_job", "wrong_commit"])
def test_rejects_incomplete_or_incorrect_ci(problem):
    report = evidence()
    if problem == "missing_job":
        report["jobs"].pop()
    elif problem == "failed_job":
        report["jobs"][0]["conclusion"] = "failure"
    else:
        report["headSha"] = "b" * 40
    with pytest.raises(ValueError, match="all five"):
        verify_release(
            "owner/repo", SHA, "refs/tags/v0.3.0", "0.3.0", query_for(report)
        )


def test_rejects_absent_successful_run():
    with pytest.raises(ValueError, match="No successful"):
        verify_release("owner/repo", SHA, "refs/tags/v0.3.0", "0.3.0", lambda _: [])
