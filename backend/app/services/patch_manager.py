import ast
import difflib
import hashlib
import os
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath

from app.config import (
    MAX_PATCH_FILE_BYTES,
    MAX_PATCH_FILES,
    MAX_PATCH_TOTAL_BYTES,
    PROJECT_ROOT,
)


class PatchError(Exception):
    """Raised when a proposed change is invalid or unsafe to apply."""


@dataclass
class FileChange:
    path: str
    content: str
    original_hash: str | None
    applied_hash: str | None = None
    original_content: bytes | None = None
    original_mode: int | None = None


@dataclass
class PatchRecord:
    patch_id: str
    summary: str
    explanation: str
    status: str
    changes: list[FileChange] = field(default_factory=list)


class PatchManager:
    def __init__(self, project_root: Path = PROJECT_ROOT) -> None:
        self.project_root = project_root.resolve()
        self._patches: dict[str, PatchRecord] = {}

    def _resolve_path(self, relative_path: str) -> Path:
        normalized = relative_path.replace("\\", "/")
        posix_path = PurePosixPath(normalized)

        if (
            not normalized
            or posix_path.is_absolute()
            or PureWindowsPath(relative_path).is_absolute()
            or PureWindowsPath(relative_path).drive
            or any(part in {"", ".", ".."} for part in posix_path.parts)
            or any(part.lower() == ".git" for part in posix_path.parts)
            or any(
                part.lower() == ".env" or part.lower().startswith(".env.")
                for part in posix_path.parts
            )
            or any(
                part.lower()
                in {
                    ".voice2code",
                    ".venv",
                    "venv",
                    "node_modules",
                    "__pycache__",
                    ".pytest_cache",
                }
                for part in posix_path.parts
            )
            or posix_path.suffix.lower() == ".pyc"
        ):
            raise PatchError(f"Unsafe project-relative path: {relative_path}")

        target = self.project_root.joinpath(*posix_path.parts)
        resolved = target.resolve()

        if not resolved.is_relative_to(self.project_root):
            raise PatchError(f"Path escapes the project: {relative_path}")

        if target.exists() and (target.is_symlink() or not target.is_file()):
            raise PatchError(f"Not a regular file: {relative_path}")

        for parent in target.parents:
            if parent == self.project_root:
                break
            if parent.is_symlink():
                raise PatchError(
                    f"Symlink directory is not allowed: {relative_path}"
                )

        return target

    def create(
        self,
        changes: dict[str, str],
        summary: str,
        explanation: str,
    ) -> dict:
        if not changes or len(changes) > MAX_PATCH_FILES:
            raise PatchError(
                f"Patch must contain between 1 and {MAX_PATCH_FILES} files"
            )

        if not summary.strip() or len(summary) > 500 or len(explanation) > 5000:
            raise PatchError("Patch summary or explanation is empty or too long")

        total_size = 0
        original_size = 0
        prepared: list[FileChange] = []
        diffs: list[str] = []
        seen_paths: set[str] = set()

        for relative_path, content in changes.items():
            if not isinstance(content, str):
                raise PatchError("Changed file content must be UTF-8 text")

            encoded = content.encode("utf-8")
            total_size += len(encoded)

            if len(encoded) > MAX_PATCH_FILE_BYTES:
                raise PatchError("Changed file exceeds the per-file size limit")

            target = self._resolve_path(relative_path)
            normalized = str(target).casefold()

            if normalized in seen_paths:
                raise PatchError("Patch contains duplicate file paths")

            seen_paths.add(normalized)

            if target.exists() and target.stat().st_size > MAX_PATCH_FILE_BYTES:
                raise PatchError("Original file exceeds the per-file size limit")

            old_bytes = target.read_bytes() if target.exists() else None
            original_size += len(old_bytes or b"")

            if original_size > MAX_PATCH_TOTAL_BYTES:
                raise PatchError("Patch originals exceed the total size limit")

            try:
                old_text = (
                    old_bytes.decode("utf-8")
                    if old_bytes is not None
                    else ""
                )
            except UnicodeDecodeError as exc:
                raise PatchError(
                    f"File is not valid UTF-8 text: {relative_path}"
                ) from exc

            old_hash = (
                hashlib.sha256(old_bytes).hexdigest()
                if old_bytes is not None
                else None
            )

            prepared.append(
                FileChange(
                    relative_path,
                    content,
                    old_hash,
                    original_content=old_bytes,
                    original_mode=(
                        target.stat().st_mode if target.exists() else None
                    ),
                )
            )

            diffs.extend(
                difflib.unified_diff(
                    old_text.splitlines(keepends=True),
                    content.splitlines(keepends=True),
                    fromfile=(
                        f"a/{relative_path}"
                        if old_bytes is not None
                        else "/dev/null"
                    ),
                    tofile=f"b/{relative_path}",
                )
            )

        if total_size > MAX_PATCH_TOTAL_BYTES:
            raise PatchError("Patch exceeds the total size limit")

        patch_id = str(uuid.uuid4())
        record = PatchRecord(
            patch_id,
            summary,
            explanation,
            "proposed",
            prepared,
        )

        self._patches[patch_id] = record

        return self._view(record, "".join(diffs))

    def get(self, patch_id: str) -> dict | None:
        record = self._patches.get(patch_id)

        return (
            self._view(record, self._make_diff(record))
            if record
            else None
        )

    def reject(self, patch_id: str) -> dict:
        record = self._required(patch_id)

        if record.status != "proposed":
            raise PatchError(
                f"Cannot reject a patch in state '{record.status}'"
            )

        record.status = "rejected"

        return self._view(record, self._make_diff(record))

    def _validate_python_files(self, record: PatchRecord) -> None:
        """
        Validate every proposed Python file before writing any file.
        ast.parse checks syntax without executing the proposed code.
        """
        for change in record.changes:
            if Path(change.path).suffix.lower() != ".py":
                continue

            try:
                ast.parse(change.content, filename=change.path)
            except SyntaxError as exc:
                raise PatchError(
                    f"Invalid Python syntax in {change.path} "
                    f"at line {exc.lineno}: {exc.msg}"
                ) from exc

    def apply(self, patch_id: str) -> dict:
        record = self._required(patch_id)

        if record.status != "proposed":
            raise PatchError(
                f"Cannot approve a patch in state '{record.status}'"
            )

        # Validate all Python files before modifying the project.
        self._validate_python_files(record)

        targets = [
            (change, self._resolve_path(change.path))
            for change in record.changes
        ]

        # Verify that no original file has changed since proposal creation.
        for change, target in targets:
            current = target.read_bytes() if target.exists() else None

            current_hash = (
                hashlib.sha256(current).hexdigest()
                if current is not None
                else None
            )

            if current_hash != change.original_hash:
                raise PatchError(
                    f"File changed since proposal: {change.path}"
                )

        written: list[tuple[FileChange, Path]] = []

        try:
            for change, target in targets:
                target.parent.mkdir(parents=True, exist_ok=True)

                # Recheck path safety before writing.
                self._resolve_path(change.path)

                temp_name: str | None = None

                try:
                    with tempfile.NamedTemporaryFile(
                        mode="wb",
                        dir=target.parent,
                        delete=False,
                    ) as temp_file:
                        temp_name = temp_file.name
                        temp_file.write(change.content.encode("utf-8"))
                        temp_file.flush()
                        os.fsync(temp_file.fileno())

                    if change.original_mode is not None:
                        os.chmod(temp_name, change.original_mode)

                    os.replace(temp_name, target)

                    change.applied_hash = hashlib.sha256(
                        change.content.encode("utf-8")
                    ).hexdigest()

                    written.append((change, target))

                finally:
                    if temp_name and os.path.exists(temp_name):
                        os.unlink(temp_name)

        except (OSError, PatchError) as exc:
            for change, target in reversed(written):
                self._restore(change, target)

            raise PatchError(
                "Patch application failed; written files were restored"
            ) from exc

        record.status = "applied"

        return self._view(record, self._make_diff(record))

    def rollback(self, patch_id: str) -> dict:
        record = self._required(patch_id)

        if record.status != "applied":
            raise PatchError(
                f"Cannot roll back a patch in state '{record.status}'"
            )

        # Verify that no file was changed after patch application.
        for change in record.changes:
            target = self._resolve_path(change.path)
            current = target.read_bytes() if target.exists() else None

            current_hash = (
                hashlib.sha256(current).hexdigest()
                if current is not None
                else None
            )

            if current_hash != change.applied_hash:
                raise PatchError(
                    f"File changed after patch application: {change.path}"
                )

        for change in reversed(record.changes):
            self._restore(
                change,
                self._resolve_path(change.path),
            )

        record.status = "rolled_back"

        return self._view(record, self._make_diff(record))

    def _restore(self, change: FileChange, target: Path) -> None:
        if change.original_content is None:
            target.unlink(missing_ok=True)
            return

        target.parent.mkdir(parents=True, exist_ok=True)
        temp_name: str | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=target.parent,
                delete=False,
            ) as temp_file:
                temp_name = temp_file.name
                temp_file.write(change.original_content)
                temp_file.flush()
                os.fsync(temp_file.fileno())

            if change.original_mode is not None:
                os.chmod(temp_name, change.original_mode)

            os.replace(temp_name, target)

        finally:
            if temp_name and os.path.exists(temp_name):
                os.unlink(temp_name)

    def _required(self, patch_id: str) -> PatchRecord:
        record = self._patches.get(patch_id)

        if record is None:
            raise PatchError("Patch not found")

        return record

    def _make_diff(self, record: PatchRecord) -> str:
        lines: list[str] = []

        for change in record.changes:
            target = self._resolve_path(change.path)
            old_bytes = change.original_content

            if old_bytes is None and change.original_hash is not None:
                old_bytes = target.read_bytes() if target.exists() else b""

            old_text = old_bytes.decode("utf-8") if old_bytes else ""

            lines.extend(
                difflib.unified_diff(
                    old_text.splitlines(keepends=True),
                    change.content.splitlines(keepends=True),
                    fromfile=(
                        f"a/{change.path}"
                        if old_bytes is not None
                        else "/dev/null"
                    ),
                    tofile=f"b/{change.path}",
                )
            )

        return "".join(lines)

    @staticmethod
    def _view(record: PatchRecord, diff: str) -> dict:
        return {
            "patch_id": record.patch_id,
            "summary": record.summary,
            "explanation": record.explanation,
            "status": record.status,
            "diff": diff,
            "files": [change.path for change in record.changes],
        }