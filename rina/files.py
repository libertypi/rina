import fnmatch
import logging
import os
import re
from collections import deque
from pathlib import Path
from typing import Generator

from . import Config
from .utils import stderr_write, strftime

logger = logging.getLogger(__name__)


class DiskScanner:
    exts: set = None
    newer: float = None

    def __init__(
        self,
        *,
        ftype: str = "file",
        exts: set = None,
        recursive: bool = True,
        include: str = None,
        exclude: str = None,
        exclude_dir: str = None,
        newer: float = None,
    ) -> None:
        """
        Initialize a DiskScanner for scanning directories with various filters.

        Parameters:
         - ftype (str): Type of items to return in `scandir` and to apply glob
           and time filters ('file' or 'dir').
         - exts (set): File extensions (lower case without leading dot)
           to include, e.g., {"mp4", "wmv"}.
         - recursive (bool): If True, scan directories recursively.
         - include (str): Glob pattern for <ftype> to include.
         - exclude (str): Glob pattern for <ftype> to exclude.
         - exclude_dir (str): Glob pattern for directories to exclude.
         - newer (float): Timestamp; <ftype> newer than this will be included.
        """
        self.filefilters = []
        self.dirfilters = []
        if ftype == "file":
            outputfilters = self.filefilters
        elif ftype == "dir":
            outputfilters = self.dirfilters
        else:
            raise ValueError(f"Invalid ftype: Expected 'file' or 'dir', not '{ftype}'.")
        self.ftype = ftype
        self.recursive = recursive

        if exts is not None:
            assert isinstance(exts, set), "expect `exts` to be 'set'"
            self.exts = exts
            self.filefilters.append(self._ext_filter)
        if include is not None:
            outputfilters.append(self._get_glob_filter(include))
        if exclude is not None:
            outputfilters.append(self._get_glob_filter(exclude, True))
        if exclude_dir is not None:
            self.dirfilters.append(self._get_glob_filter(exclude_dir, True))
        if newer is not None:
            self.newer = newer
            outputfilters.append(self._mtime_filter)

    @staticmethod
    def _get_glob_filter(glob: str, inverse: bool = False):
        """
        Create a glob-based filter function for file inclusion or exclusion.

        Parameters:
         - glob (str): A glob pattern to match file names against.
         - inverse (bool): If True, exclude files that match the pattern.
        """
        glob = re.compile(fnmatch.translate(glob), re.IGNORECASE).match
        if inverse:
            return lambda es: (e for e in es if not glob(e.name))
        else:
            return lambda es: (e for e in es if glob(e.name))

    def _ext_filter(self, es):
        """
        Filter function to include files based on their extensions. Extension is
        everything from the last dot to the end, ignoring leading dots.
        """
        exts = self.exts
        for e in es:
            p = e.name.rpartition(".")
            if p[0].rstrip(".") and p[2].lower() in exts:
                yield e

    def _mtime_filter(self, es):
        """Filter function to include files based on their mtime."""
        newer = self.newer
        for e in es:
            try:
                if e.stat().st_mtime >= newer:
                    yield e
            except OSError:
                pass

    def scandir(self, root) -> Generator[os.DirEntry, None, None]:
        """
        Scan a directory and yield files or directories based on filters and
        type.

        Parameters:
         - root: Directory path to start scanning.

        Yields:
         - os.DirEntry: Directory entries matching the specified filters and
           type.
        """
        dirs = []
        files = []
        output = files if self.ftype == "file" else dirs
        dirfilters = self.dirfilters
        filefilters = self.filefilters
        recursive = self.recursive
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
                    for f in filefilters:
                        files[:] = f(output)
            except OSError as e:
                logger.error(e)
            else:
                que.extend(dirs)
                yield from output
            if not recursive:
                break

    def walk(self, root):
        """
        Walk through directories, applying filters and yielding both files and
        directories.

        Parameters:
         - root: Directory path to start walking.

        Yields:
         - Tuple[List, List]: A tuple containing lists of directories and files.
        """
        assert self.ftype == "file", 'Calling walk() when ftype != "file"'
        dirfilters = self.dirfilters
        filefilters = self.filefilters
        recursive = self.recursive
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
                    for f in filefilters:
                        files[:] = f(files)
            except OSError as e:
                logger.error(e)
            else:
                que.extend(dirs)
                yield dirs, files
            if not recursive:
                break


def get_scanner(args, ftype: str = "file", exts=None):
    """
    Construct a DiskScanner based on arguments.

    :type args: argparse.Namespace
    """
    return DiskScanner(
        ftype=ftype,
        exts=exts,
        recursive=args.recursive,
        include=args.include,
        exclude=args.exclude,
        exclude_dir=args.exclude_dir,
        newer=args.newer,
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
                try:
                    is_dir = e.is_dir(follow_symlinks=False)
                except OSError:
                    is_dir = False
                if is_dir:
                    dirs.append(e)
                    continue
                try:
                    mtime = e.stat().st_mtime
                except OSError:
                    continue
                if mtime > newest:
                    newest = mtime
    except OSError as e:
        logger.error(e)
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
                if not Config.DRYRUN:
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
            logger.error(e)
    return newest, total, updated
