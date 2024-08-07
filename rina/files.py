import fnmatch
import logging
import os
import re
from pathlib import Path
from typing import Generator

from .utils import Config, stderr_write, strftime

logger = logging.getLogger(__name__)
_EADIR = "@eaDir"  # Synology hidden directory


class DiskScanner:
    exts: set = None
    newer: float = None

    def __init__(
        self,
        *,
        exts: set = None,
        recursive: bool = True,
        includes: list = None,
        excludes: list = None,
        exclude_dirs: list = None,
        newer: float = None,
    ) -> None:
        """
        Initialize a DiskScanner for scanning directories with various filters.

        Parameters:
         - exts (set): File extensions (lower case without leading dot)
           to include, e.g., {"mp4", "wmv"}.
         - recursive (bool): If True, scan directories recursively.
         - includes (list): Glob patterns for files to include.
         - excludes (list): Glob patterns for files to exclude.
         - exclude_dirs (list): Glob patterns for directories to exclude.
         - newer (float): Timestamp; files newer than this will be included.
        """
        self.filters = []
        self.dirfilters = []
        self.recursive = recursive

        if exts is not None:
            assert isinstance(exts, set), "expect `exts` to be 'set'"
            self.exts = exts
            self.filters.append(self._ext_filter)
        if includes is not None:
            self.filters.append(self._get_glob_filter(includes))
        if excludes is not None:
            self.filters.append(self._get_glob_filter(excludes, True))
        if exclude_dirs is not None:
            self.dirfilters.append(self._get_glob_filter(exclude_dirs, True))
        if newer is not None:
            self.newer = newer
            self.filters.append(self._mtime_filter)

    @staticmethod
    def _get_glob_filter(globs: list, inverse: bool = False):
        """
        Create a glob-based filter function for file inclusion or exclusion.

        Parameters:
         - globs (list[str]): A list of globs to match file names against.
         - inverse (bool): If True, exclude files that match the pattern.
        """
        globs = re.compile("|".join(map(fnmatch.translate, globs)), re.I).match
        if inverse:
            return lambda es: (e for e in es if not globs(e.name))
        else:
            return lambda es: (e for e in es if globs(e.name))

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

    def scandir(
        self, root, yield_dirs: bool = False
    ) -> Generator[os.DirEntry, None, None]:
        """
        Scans a directory, yielding filtered files or directories.

        Parameters:
         - root: The path of the directory to scan.
         - yield_dirs: If True, filters and yields directories instead of files.
           Defaults to False.

        Yields:
         - os.DirEntry: Directory entries matching the specified filters and
           type.
        """
        dirs = []
        files = []
        output = dirs if yield_dirs else files
        dirfilters = self.dirfilters
        filters = self.filters
        recursive = self.recursive
        stack = [root]
        while stack:
            root = stack.pop()
            dirs.clear()
            files.clear()
            try:
                with os.scandir(root) as it:
                    for e in it:
                        try:
                            is_dir = e.is_dir(follow_symlinks=False)
                        except OSError:
                            is_dir = False
                        if not is_dir:
                            files.append(e)
                        elif e.name != _EADIR:
                            dirs.append(e)
                    for f in dirfilters:
                        dirs[:] = f(dirs)
                    stack.extend(reversed(dirs))
                    for f in filters:
                        output[:] = f(output)
            except OSError as e:
                logger.error(e)
            else:
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
        dirfilters = self.dirfilters
        filters = self.filters
        recursive = self.recursive
        stack = [root]
        while stack:
            root = stack.pop()
            dirs = []
            files = []
            try:
                with os.scandir(root) as it:
                    for e in it:
                        try:
                            is_dir = e.is_dir(follow_symlinks=False)
                        except OSError:
                            is_dir = False
                        if not is_dir:
                            files.append(e)
                        elif e.name != _EADIR:
                            dirs.append(e)
                    for f in dirfilters:
                        dirs[:] = f(dirs)
                    for f in filters:
                        files[:] = f(files)
            except OSError as e:
                logger.error(e)
            else:
                stack.extend(reversed(dirs))
                yield dirs, files
            if not recursive:
                break


def get_scanner(args, exts=None):
    """
    Construct a DiskScanner based on arguments.

    :type args: argparse.Namespace
    """
    return DiskScanner(
        exts=exts,
        recursive=args.recursive,
        includes=args.include,
        excludes=args.exclude,
        exclude_dirs=args.exclude_dir,
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
                if not is_dir:
                    try:
                        mtime = e.stat().st_mtime
                    except OSError:
                        continue
                    if mtime > newest:
                        newest = mtime
                elif e.name != _EADIR:
                    dirs.append(e)
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
