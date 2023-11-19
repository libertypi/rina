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

from rina.scandir import FileScanner, get_scanner
from rina.utils import SEP_BOLD, AVInfo, Status, get_choice_as_int, stderr_write

EXTS = {"avi", "m2ts", "m4v", "mkv", "mov", "mp4", "mpeg", "mpg", "ts", "wmv"}


class VideoGroup(AVInfo):
    keywidth = 6

    def __init__(self, source: Tuple[Path], output: Path) -> None:
        self.source = source
        self.output = output
        self.applied = False
        self.result = {
            "Source": source,
            "Output": output,
        }
        try:
            diff_streams = tuple(self._find_diff())
        except Exception as e:
            self.status = Status.ERROR
            self.result["Error"] = str(e)
            return
        if diff_streams:
            self.status = Status.WARNING
            self.result["Diff"] = diff_streams
        else:
            self.status = Status.UPDATED

    def _find_diff(self):
        """
        Find videos with different streams. If such differences are found, yield
        formated lines representing filenames and stream details.
        """
        diffs = []
        first = None
        for file in self.source:
            stream = subprocess.run(
                (
                    ffprobe,
                    "-loglevel",
                    "fatal",
                    "-show_entries",
                    "stream=index,codec_name,width,height,time_base",
                    "-print_format",
                    "json",
                    file,
                ),
                capture_output=True,
                text=True,
                check=True,
            ).stdout
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
                (
                    ffmpeg,
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    tmpfile,
                    "-c",
                    "copy",
                    self.output,
                ),
                check=True,
            )
        except subprocess.CalledProcessError as e:
            logging.error(e)
            self.output.unlink(missing_ok=True)
        else:
            self.applied = True
        finally:
            os.unlink(tmpfile)

    def remove_source(self):
        if not self.applied:
            raise RuntimeError("Calling `remove_source` before successfully `apply`.")
        for file in self.source:
            try:
                os.unlink(file)
            except OSError as e:
                logging.error(e)
            else:
                stderr_write(f"Remove: {file}\n")


def find_groups(root, scanner: FileScanner = None):
    """
    Find groups of video files under the same directory with consecutive
    numbering and yields VideoGroup objects.
    """
    if scanner is None:
        scanner = FileScanner(exts=EXTS)
    # Stores seen file names to avoid conflicts
    seen = set()
    groups = defaultdict(dict)
    matcher = re.compile(
        r"""
        (?P<pre>.+?)
        (?P<sep>[\s._-]+(?:part|chunk|vol|cd|dvd)?[\s._-]*)
        (?P<num>0?[1-9]|[1-9][0-9]|[a-z])\s*
        (?P<ext>\.[^.]+)
        """,
        flags=re.VERBOSE | re.IGNORECASE,
    ).fullmatch

    for _, files in scanner.walk(root):
        groups.clear()
        seen.clear()
        for e in files:
            name = e.name
            seen.add(name)
            m = matcher(name)
            if not m:
                continue
            n = m["num"]
            # if n is a-z, convert to 1-26
            isdigit = n.isdigit()
            n = int(n) if isdigit else ord(n.lower()) - 96
            groups[(m["pre"], m["sep"], m["ext"].lower(), isdigit)][n] = e.path

        for k, v in groups.items():
            n = len(v)
            if 1 < n == max(v):
                # consecutive numbers starting from 1
                name = k[0] + k[2]  # pre + ext
                if name in seen:
                    continue
                source = tuple(Path(v[i]) for i in range(1, n + 1))
                yield VideoGroup(source=source, output=source[0].with_name(name))


if os.name == "nt":
    ffmpeg = "ffmpeg.exe"
    ffprobe = "ffprobe.exe"
else:
    ffmpeg = "ffmpeg"
    ffprobe = "ffprobe"


def _find_ffmpeg(args_ffmpeg):
    global ffmpeg, ffprobe

    if args_ffmpeg:
        args_ffmpeg = Path(args_ffmpeg)
        if args_ffmpeg.is_dir():
            ffmpeg = args_ffmpeg.joinpath(ffmpeg)
            ffprobe = args_ffmpeg.joinpath(ffprobe)
        else:
            ffmpeg = args_ffmpeg
            ffprobe = args_ffmpeg.with_name(ffprobe)

    for exe in ffmpeg, ffprobe:
        if not shutil.which(exe):
            logging.error(
                "{exe} not found. Please be sure it can be found in $PATH or the directory passed via '-f' option."
            )
            sys.exit(1)


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
    _find_ffmpeg(args.ffmpeg)

    results = set()
    for group in find_groups(args.source, get_scanner(args, exts=EXTS)):
        group.print()
        results.add(group)

    if not results:
        stderr_write("Scan finished. No change can be made.\n")
        return
    stderr_write(
        "{}\nScan finished, {} files can be concatenated into {} files.\n".format(
            SEP_BOLD, sum(len(v.source) for v in results), len(results)
        )
    )

    if not args.quiet:
        results = set(user_filter(results, "Proceed with concatenation?", False))

    # problematic groups
    skips = {g for g in results if g.status != Status.UPDATED}
    if not args.quiet:
        # remove those user choses to keep
        skips = skips.difference(
            user_filter(skips, "Concat these files anyway (not recommended)?")
        )
    results.difference_update(skips)

    # apply concatenation
    for group in results:
        group.apply()

    # remove sources that have been successfully concatenated
    results = {g for g in results if g.applied}
    if not args.quiet:
        for group in user_filter(
            results, "Delete all successfully concatenated source files?"
        ):
            group.remove_source()
