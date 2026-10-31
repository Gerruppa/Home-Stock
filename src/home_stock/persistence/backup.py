"""The Backup: a copy of the database taken at every start, before migrations."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

KEEP_BACKUPS = 30


def backup_database(db_path: Path, backups_dir: Path, now: datetime | None = None) -> Path | None:
    """Copy ``db_path`` into ``backups_dir`` and drop all but the newest KEEP_BACKUPS copies; None when there is no
    database yet."""
    if not db_path.exists():
        return None
    backups_dir.mkdir(parents=True, exist_ok=True)
    # UTC, so names keep sorting oldest first when the local clock goes back (end of DST)
    stamp = f"{now or datetime.now(UTC):%Y%m%d-%H%M%S}Z"
    target = _unused_path(backups_dir, f"{db_path.stem}-{stamp}", db_path.suffix)
    # SQLite's backup API gives a consistent copy even if another connection is open
    source = sqlite3.connect(db_path)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    # Only names this function makes, so a file the user put here is neither counted nor removed
    for old in sorted(backups_dir.glob(f"{db_path.stem}-????????-??????Z*{db_path.suffix}"))[:-KEEP_BACKUPS]:
        old.unlink()
    return target


def _unused_path(backups_dir: Path, stem: str, suffix: str) -> Path:
    # "_01" sorts after ".", so a same-second copy still sorts after the first one
    candidate = backups_dir / f"{stem}{suffix}"
    counter = 1
    while candidate.exists():
        candidate = backups_dir / f"{stem}_{counter:02d}{suffix}"
        counter += 1
    return candidate
