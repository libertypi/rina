import os
from pathlib import Path

from avinfo._utils import stderr_write, strftime


def update_dir_mtime(top_dir: Path):
    total = success = 0

    def probe_dir(root):
        nonlocal total, success

        total += 1
        newest = 0
        dirs = []

        with os.scandir(root) as it:
            for entry in it:
                if entry.is_dir(follow_symlinks=False):
                    if entry.name[0] not in "#@":
                        dirs.append(entry)
                else:
                    mtime = entry.stat().st_mtime
                    if mtime > newest:
                        newest = mtime

        for entry in dirs:
            mtime = probe_dir(entry)
            if mtime > newest:
                newest = mtime

        if newest:
            stat = root.stat()
            if newest != stat.st_mtime:
                try:
                    os.utime(root, (stat.st_atime, newest))
                except OSError as e:
                    stderr_write(f"{e}\n")
                else:
                    success += 1
                    stderr_write(
                        "{} => {}: {}\n".format(
                            strftime(stat.st_mtime), strftime(newest), os.fspath(root)
                        )
                    )
        return newest

    stderr_write("Updating directory timestamps...\n")

    if not isinstance(top_dir, Path):
        top_dir = Path(top_dir)
    try:
        probe_dir(top_dir)
    except OSError as e:
        stderr_write(f"error occurred scanning {top_dir}: {e}\n")
    else:
        stderr_write(f"Finished. {total} dirs scanned, {success} updated.\n")
