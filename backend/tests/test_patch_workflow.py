from pathlib import Path

import pytest

from app.services.patch_manager import PatchError, PatchManager


def test_patch_requires_approval_and_can_be_rejected(tmp_path: Path):
    original = tmp_path / "example.txt"
    original.write_text("before\n", encoding="utf-8")
    manager = PatchManager(tmp_path)

    proposal = manager.create(
        {"example.txt": "after\n"}, "Update example", "A test patch"
    )

    assert proposal["status"] == "proposed"
    assert "before" in proposal["diff"] and "after" in proposal["diff"]
    assert original.read_text(encoding="utf-8") == "before\n"

    rejected = manager.reject(proposal["patch_id"])
    assert rejected["status"] == "rejected"

    with pytest.raises(PatchError):
        manager.apply(proposal["patch_id"])


def test_approved_patch_can_be_rolled_back(tmp_path: Path):
    original = tmp_path / "example.txt"
    original.write_text("before\n", encoding="utf-8")
    manager = PatchManager(tmp_path)

    proposal = manager.create(
        {"example.txt": "after\n"}, "Update", "Explanation"
    )

    applied = manager.apply(proposal["patch_id"])
    assert applied["status"] == "applied"
    assert original.read_text(encoding="utf-8") == "after\n"

    rolled_back = manager.rollback(proposal["patch_id"])
    assert rolled_back["status"] == "rolled_back"
    assert original.read_text(encoding="utf-8") == "before\n"


@pytest.mark.parametrize(
    "path",
    [
        "../outside.txt",
        "C:\\outside.txt",
        ".env",
        "backend/.env.local",
        ".git/config",
        ".voice2code/state",
    ],
)
def test_patch_rejects_traversal_and_private_paths(
    tmp_path: Path, path: str
):
    manager = PatchManager(tmp_path)

    with pytest.raises(PatchError):
        manager.create({path: "unsafe"}, "Unsafe", "Must be blocked")


def test_patch_refuses_to_overwrite_a_file_changed_after_proposal(
    tmp_path: Path,
):
    target = tmp_path / "example.txt"
    target.write_text("before\n", encoding="utf-8")
    manager = PatchManager(tmp_path)

    proposal = manager.create(
        {"example.txt": "proposed\n"}, "Update", "Explanation"
    )

    target.write_text("user change\n", encoding="utf-8")

    with pytest.raises(PatchError, match="File changed since proposal"):
        manager.apply(proposal["patch_id"])

    assert target.read_text(encoding="utf-8") == "user change\n"


def test_rollback_refuses_to_overwrite_a_later_user_change(
    tmp_path: Path,
):
    target = tmp_path / "example.txt"
    target.write_text("before\n", encoding="utf-8")
    manager = PatchManager(tmp_path)

    proposal = manager.create(
        {"example.txt": "applied\n"}, "Update", "Explanation"
    )

    manager.apply(proposal["patch_id"])
    target.write_text("later user edit\n", encoding="utf-8")

    with pytest.raises(
        PatchError, match="File changed after patch application"
    ):
        manager.rollback(proposal["patch_id"])

    assert target.read_text(encoding="utf-8") == "later user edit\n"


def test_invalid_python_patch_is_rejected_without_creating_file(
    tmp_path: Path,
):
    manager = PatchManager(tmp_path)

    proposal = manager.create(
        {"broken.py": 'def greet(name):\n    return f"Hello, {name}\n'},
        "Create greeting function",
        "Invalid Python syntax test",
    )

    with pytest.raises(PatchError, match="Invalid Python syntax"):
        manager.apply(proposal["patch_id"])

    assert not (tmp_path / "broken.py").exists()


def test_invalid_python_patch_does_not_modify_existing_file(
    tmp_path: Path,
):
    target = tmp_path / "existing.py"
    original_content = "def greet(name):\n    return 'Hello'\n"
    target.write_text(original_content, encoding="utf-8")

    manager = PatchManager(tmp_path)

    proposal = manager.create(
        {"existing.py": 'def greet(name):\n    return f"Hello, {name\n'},
        "Update greeting function",
        "Invalid Python syntax test",
    )

    with pytest.raises(PatchError, match="Invalid Python syntax"):
        manager.apply(proposal["patch_id"])

    assert target.read_text(encoding="utf-8") == original_content


def test_valid_python_patch_can_be_applied(tmp_path: Path):
    manager = PatchManager(tmp_path)

    valid_code = (
        "def greet(name: str) -> str:\n"
        '    return f"Hello, {name}"\n'
    )

    proposal = manager.create(
        {"hello.py": valid_code},
        "Create greeting function",
        "Valid Python syntax test",
    )

    result = manager.apply(proposal["patch_id"])

    assert result["status"] == "applied"
    assert (tmp_path / "hello.py").read_text(
        encoding="utf-8"
    ) == valid_code
