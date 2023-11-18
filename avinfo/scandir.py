import fnmatch
import os
import re
from collections import deque
from pathlib import Path
from typing import Generator

from avinfo.utils import stderr_write, strftime


class FileScanner:
    def __init__(
        self,
        recursive: bool = True,
        exts: set = None,
        include: str = None,
        exclude: str = None,
        exclude_dir: str = None,
        newer: int = None,
    ) -> None:
        """
        exts: a set of lower extensions without leading dot, e.g. {"mp4", "wmv"}
        """

        self.recursive = recursive
        # dirfilters filter only dirs, and mainfilters filter the output
        self.mainfilters = mainfilters = []
        self.dirfilters = []

        # extension filter
        if exts is not None:
            mainfilters.append(self._get_ext_filter(exts))

        # globs
        if include is not None:
            mainfilters.append(self._get_glob_filter(include))
        if exclude is not None:
            mainfilters.append(self._get_glob_filter(exclude, True))
        if exclude_dir is not None:
            self.dirfilters.append(self._get_glob_filter(exclude_dir, True))

        # exclude mtime older than `age`
        if newer is not None:
            mainfilters.append(lambda es: (e for e in es if e.stat().st_mtime >= newer))

    @staticmethod
    def _get_ext_filter(exts):
        if not isinstance(exts, (set, frozenset)):
            exts = frozenset(exts)

        def _ext_filter(es):
            for e in es:
                parts = e.name.rpartition(".")
                if parts[0] and parts[2].lower() in exts:
                    yield e

        return _ext_filter

    @staticmethod
    def _get_glob_filter(glob: str, inverse: bool = False):
        glob = re.compile(fnmatch.translate(glob)).match
        if inverse:
            return lambda es: (e for e in es if not glob(e.name))
        else:
            return lambda es: (e for e in es if glob(e.name))

    def scandir(self, root, ftype: str = "file") -> Generator[os.DirEntry, None, None]:
        files = []
        dirs = []
        if ftype == "file":
            output = files
        elif ftype == "dir":
            output = dirs
        else:
            raise ValueError(f"Invalid ftype: '{ftype}'. Expected 'file' or 'dir'.")
        recursive = self.recursive
        dirfilters = self.dirfilters
        mainfilters = self.mainfilters
        que = deque((root,))
        while que:
            root = que.popleft()
            dirs.clear()
            files.clear()
            try:
                with os.scandir(root) as it:
                    for e in it:
                        try:
                            is_dir = e.is_dir(follow_symlinks=False)
                        except OSError:
                            is_dir = False
                        (dirs if is_dir else files).append(e)
                    for f in dirfilters:
                        dirs[:] = f(dirs)
                    for f in mainfilters:
                        output[:] = f(output)
            except OSError as e:
                stderr_write(f"{e}\n")
            else:
                que.extend(dirs)
                yield from output
            if not recursive:
                break

    def walk(self, root):
        recursive = self.recursive
        dirfilters = self.dirfilters
        mainfilters = self.mainfilters
        que = deque((root,))
        while que:
            root = que.popleft()
            dirs = []
            files = []
            try:
                with os.scandir(root) as it:
                    for e in it:
                        try:
                            is_dir = e.is_dir(follow_symlinks=False)
                        except OSError:
                            is_dir = False
                        (dirs if is_dir else files).append(e)
                    for f in dirfilters:
                        dirs[:] = f(dirs)
                    for f in mainfilters:
                        files[:] = f(files)
            except OSError as e:
                stderr_write(f"{e}\n")
            else:
                que.extend(dirs)
                yield dirs, files
            if not recursive:
                break


def get_scanner(args, exts: set = None):
    """
    Construct a FileScanner based on arguments.

    :type args: argparse.Namespace
    """
    return FileScanner(
        recursive=args.recursive,
        exts=exts,
        include=args.include,
        exclude=args.exclude,
        exclude_dir=args.exclude_dir,
        newer=args.time,
    )


def update_dir_mtime(root):
    """
    Update the modification times of directories based on the newest file they
    contain.
    """
    if not isinstance(root, Path):
        root = Path(root)
    stderr_write("Updating directory timestamps...\n")
    _, total, updated = _update_dirtime(root)
    stderr_write(f"Finished. Total: {total}. Updated: {updated}.\n")


def _update_dirtime(root, total=0, updated=0):
    """Recursive helper function to update directory modification times."""
    newest = 0
    total += 1
    dirs = []
    try:
        with os.scandir(root) as it:
            for e in it:
                if e.is_dir():
                    dirs.append(e)
                else:
                    mtime = e.stat().st_mtime
                    if mtime > newest:
                        newest = mtime
    except OSError as e:
        stderr_write(f"{e}\n")
        return 0, total, updated
    # Process subdirectories after closing the parent's file handle
    for e in dirs:
        mtime, total, updated = _update_dirtime(e, total, updated)
        if mtime > newest:
            newest = mtime
    if newest:
        try:
            stat = root.stat()
            if newest != stat.st_mtime:
                os.utime(root, (stat.st_atime, newest))
                updated += 1
                stderr_write(
                    "{} => {}: {}\n".format(
                        strftime(stat.st_mtime),
                        strftime(newest),
                        os.fspath(root),
                    )
                )
        except OSError as e:
            stderr_write(f"{e}\n")
    return newest, total, updated
