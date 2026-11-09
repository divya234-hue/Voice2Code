import json
from collections import Counter
from pathlib import Path


REQUIRED_FIELDS = {
    "source_repo",
    "issue",
    "tool_steps",
    "patch",
    "resolved",
}


def audit_trajectory_jsonl(path: Path) -> dict:
    accepted = 0
    rejected = Counter()
    repositories = Counter()

    with Path(path).open(encoding="utf-8") as stream:
        for line in stream:
            try:
                sample = json.loads(line)

                if not isinstance(sample, dict):
                    raise ValueError("invalid record")

                if not REQUIRED_FIELDS.issubset(sample):
                    raise ValueError("missing fields")

                if not sample["source_repo"] or not sample["issue"]:
                    raise ValueError("missing provenance or issue")

                if sample["resolved"] is not True:
                    raise ValueError("unsuccessful trajectory")

                patch = sample["patch"]

                if not isinstance(patch, str) or not patch.startswith("diff --git "):
                    raise ValueError("invalid patch")

                steps = sample["tool_steps"]

                if not isinstance(steps, list) or not steps:
                    raise ValueError("missing tool steps")

                for step in steps:
                    if not isinstance(step, dict):
                        raise ValueError("invalid tool step")

                    if not {"tool", "request", "result"}.issubset(step):
                        raise ValueError("incomplete tool step")

                if "test_patch" in sample:
                    raise ValueError("verification label leakage")

                accepted += 1
                repositories[sample["source_repo"]] += 1

            except (ValueError, TypeError, AttributeError) as error:
                rejected[str(error)] += 1

    return {
        "accepted": accepted,
        "rejected": dict(rejected),
        "repositories": dict(repositories),
    }