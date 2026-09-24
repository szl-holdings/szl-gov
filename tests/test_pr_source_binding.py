from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = (
    ".github/workflows/gates.yml",
    ".github/workflows/base-python-ci.yml",
    ".github/workflows/forbidden-domain.yml",
)


def test_pr_workflows_bind_and_prove_exact_event_source():
    for relative_path in WORKFLOWS:
        text = (ROOT / relative_path).read_text()
        assert "github.event.pull_request.head.sha || github.sha" in text, relative_path
        assert "ref: ${{ env.SOURCE_REVISION }}" in text, relative_path
        assert "persist-credentials: false" in text, relative_path
        assert "git rev-parse HEAD" in text, relative_path
        assert '"$SOURCE_REVISION"' in text, relative_path


def test_every_truth_check_checkout_is_source_bound():
    text = (ROOT / ".github/workflows/gates.yml").read_text()
    checkout_count = text.count("uses: actions/checkout@")
    bound_checkout_count = text.count("ref: ${{ env.SOURCE_REVISION }}")
    proof_count = text.count("name: Prove exact event source")

    assert checkout_count == 5
    assert bound_checkout_count == checkout_count
    assert proof_count == checkout_count
