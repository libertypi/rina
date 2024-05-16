import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Tuple

from .files import DiskScanner, get_scanner
from .utils import SEP_BOLD, AVInfo, Config, Status, get_choice_as_int, stderr_write

logger = logging.getLogger(__name__)

if os.name == "nt":
    FFMPEG = "ffmpeg.exe"
    FFPROBE = "ffprobe.exe"
else:
    FFMPEG = "ffmpeg"
    FFPROBE = "ffprobe"
EXTS = {"avi", "m2ts", "m4v", "mkv", "mov", "mp4", "mpeg", "mpg", "ts", "wmv"}


class ConcatGroup(AVInfo):
    keywidth = 7
    applied: bool = False

    def __init__(
        self, source: Tuple[Path], output: Path, ffmpeg=FFMPEG, ffprobe=FFPROBE
    ) -> None:
        self.source = source
        self.output = output
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe
        self.result = {
            "Source": source,
            "Output": output,
        }
        try:
            diffs = tuple(self._find_diffs())
        except Exception as e:
            self.status = Status.ERROR
            self.result["Error"] = e
            return
        if diffs:
            self.status = Status.WARNING
            self.result["Diffs"] = diffs
        else:
            self.status = Status.UPDATED

    def _find_diffs(self):
        """
        Find videos with different streams. If such differences are found, yield
        formated lines representing filenames and stream details.
        """
        diffs = []
        first = None
        for file in self.source:
            stream = subprocess.run(
                (self.ffprobe, "-loglevel", "quiet", "-show_entries",
                 "stream=index,codec_name,width,height,time_base",
                 "-print_format", "json", file),
                capture_output=True,
                text=True,
                check=True,
            ).stdout  # fmt: skip
            # a list of dicts
            stream = tuple(
                d
                for d in json.loads(stream)["streams"]
                if d["codec_name"] != "bin_data"
            )
            if first is None:
                first = stream
            elif first == stream:
                continue
            diffs.append((file, stream))

        if len(diffs) <= 1:
            return

        for file, stream in diffs:
            yield file.name
            for d in stream:
                yield "- " + "|".join(f"{k}={v}" for k, v in d.items())

    def apply(self):
        if Config.DRYRUN:
            stderr_write(f"[DRYRUN] Output: '{self.output}'\n")
            self.applied = True
            return

        tmpfd, tmpfile = tempfile.mkstemp()
        try:
            # ffmpeg escaping
            # https://www.ffmpeg.org/ffmpeg-utils.html#Quoting-and-escaping
            with os.fdopen(tmpfd, "w", encoding="utf-8") as f:
                f.writelines(
                    "file '{}'\n".format(os.fspath(p).replace("'", "'\\''"))
                    for p in self.source
                )
            subprocess.run(
                (self.ffmpeg, "-hide_banner", "-f", "concat", "-safe", "0",
                 "-i", tmpfile, "-c", "copy", self.output),
                check=True,
            )  # fmt: skip
        except subprocess.CalledProcessError as e:
            logger.error(e)
            self.output.unlink(missing_ok=True)
        else:
            self.applied = True
        finally:
            os.unlink(tmpfile)

    def remove_source(self):
        if not self.applied:
            raise RuntimeError("Calling `remove_source` before successfully `apply`.")

        if Config.DRYRUN:
            for file in self.source:
                stderr_write(f"[DRYRUN] Remove: {file}\n")
            return

        for file in self.source:
            try:
                os.unlink(file)
            except OSError as e:
                stderr_write(f"Failed to remove {file}: {e}\n")
            else:
                stderr_write(f"Remove: {file}\n")


def _find_ffmpeg(args_ffmpeg):
    if args_ffmpeg:
        args_ffmpeg = Path(args_ffmpeg)
        if args_ffmpeg.is_dir():
            exes = args_ffmpeg.joinpath(FFMPEG), args_ffmpeg.joinpath(FFPROBE)
        else:
            exes = args_ffmpeg, args_ffmpeg.with_name(FFPROBE)
    else:
        exes = FFMPEG, FFPROBE
    for e in exes:
        if not shutil.which(e):
            sys.exit(
                f"{e} not found. Please be sure it can be found in "
                "PATH or the directory passed via '-f' option."
            )
    return exes


def find_groups(root, scanner: DiskScanner = None):
    """
    Find groups of video files under the same directory with consecutive
    numbering and yields two-tuples of (source, output).
    """
    if scanner is None:
        scanner = DiskScanner(exts=EXTS)

    # Regex to find sequence numbers `seq` in the filename:
    # Filename: ABP-403-1 Title.mp4
    # lstem:    ABP-403-
    # seq:              1
    # rstem:              Title
    # ext:                      mp4
    seq_finder = re.compile(
        r"(?<![0-9])(?:0?[1-9]|[1-9][0-9])(?![0-9])|\b[A-Za-z]\b"
    ).finditer

    # Cleaners for `lstem` and `rstem`
    lcleaner = re.compile(
        r"(([-_.\s【「『｛（《\[(]+|\b)(cd|dvd|vol|part|chunk))?[-_.\s【「『｛（《\[(]*\Z",
        flags=re.IGNORECASE,
    ).sub
    rcleaner = re.compile(r"\A[-_.\s】」』｝）》\])]+").sub

    groups = defaultdict(dict)
    seen = set()  # Set to avoid output overlapping groups

    for _, files in scanner.walk(root):
        groups.clear()
        seen.clear()
        for e in files:
            # Split the filename into stem and extension
            stem, _, ext = e.name.rpartition(".")
            for m in seq_finder(stem):
                # Convert sequence to integer if it's a digit, otherwise
                # `unicode_code - offset`. Values are normalized to a 1-based
                # index and `offset` is stored in the key to distinguish types.
                seq = m[0]
                if seq.isdigit():
                    offset = 0
                    seq = int(seq)
                else:
                    # Unicode code "A": 65, "a": 97
                    offset = 64 if seq.isupper() else 96
                    seq = ord(seq) - offset
                # key: (lstem, rstem, ext, offset)
                groups[stem[: m.start()], stem[m.end() :], ext, offset][seq] = e

        for k, v in groups.items():
            m = len(v)
            # Check if sequence numbers are consecutive
            if 1 < m == max(v) and seen.isdisjoint(v.values()):
                seen.update(v.values())
                # Clean and assemble new filename parts
                newname = " ".join(
                    filter(None, (lcleaner("", k[0]), rcleaner("", k[1])))
                )
                # If there is no valid part to form a new name, use the first
                # file's name
                newname = f"{newname}.{k[2]}" if newname else f"Concat_{v[1].name}"
                # Yield the result
                source = tuple(Path(v[i]) for i in range(1, m + 1))
                yield source, source[0].with_name(newname)


def user_filter(items, question: str, initial_print: bool = True):
    """
    Interactively filter `items` based on user choices. Allows user to select,
    skip, or quit for each item in the results.
    """
    if not items:
        return
    msg = (
        f"{SEP_BOLD}\n"
        f"{question}\n"
        "1) yes\n"
        "2) no\n"
        "3) select items\n"
        "4) quit\n"
    )
    if initial_print:
        for group in items:
            group.print()
    choice = get_choice_as_int(msg, 4)
    if choice == 1:
        # yes to all
        yield from items
    elif choice == 3:
        # select items
        msg = (
            f"{SEP_BOLD}\n"
            f"Please choose an option ({{}} of {len(items)} items):\n"
            "1) select this item\n"
            "2) skip this item\n"
            "3) select this and all following items\n"
            "4) skip this and all following items\n"
            "5) quit\n"
        )
        n = 1
        stack = list(items)
        while stack:
            group = stack.pop()
            group.print()
            choice = get_choice_as_int(msg.format(n), 5)
            if choice == 1:
                # select item
                yield group
            elif choice == 3:
                # select all following
                yield group
                yield from stack
                break
            elif choice == 4:
                # skip all following
                break
            elif choice == 5:
                # quit
                sys.exit(0)
            n += 1
    elif choice == 4:
        # quit
        sys.exit(0)


def main(args):
    ffmpeg, ffprobe = _find_ffmpeg(args.ffmpeg)
    results = []
    for group in find_groups(args.source, get_scanner(args, exts=EXTS)):
        group = ConcatGroup(
            source=group[0],
            output=group[1],
            ffmpeg=ffmpeg,
            ffprobe=ffprobe,
        )
        group.print()
        results.append(group)

    if not results:
        stderr_write("Scan finished. No change can be made.\n")
        return
    stderr_write(
        "{}\nScan finished, {} files can be concatenated into {} files.\n".format(
            SEP_BOLD, sum(len(v.source) for v in results), len(results)
        )
    )

    results = set(user_filter(results, "Proceed with concatenation?", False))

    # problematic groups
    skips = {g for g in results if g.status != Status.UPDATED}
    # remove those user choses to keep
    skips = skips.difference(
        user_filter(skips, "Concat these files anyway (NOT recommended)?")
    )
    results.difference_update(skips)

    # apply concatenation
    for group in results:
        group.apply()

    # remove sources that have been successfully concatenated
    for group in user_filter(
        [g for g in results if g.applied],
        "Delete all concatenated source files (WITH CAUTION)?",
    ):
        group.remove_source()
