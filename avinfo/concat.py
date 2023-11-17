import json
import os
import os.path as op
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict

from avinfo.utils import AVInfo, Sep, Status, get_choice_as_int, stderr_write


class VideoGroup(AVInfo):
    keywidth = 6

    def __init__(self, source: tuple, output: str) -> None:
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
            yield Sep.SLIM
            yield f"filename: {op.basename(file)}"
            for d in stream:
                yield ", ".join(f"{k}: {v}" for k, v in d.items())

    def apply(self):
        tmpfd, tmpfile = tempfile.mkstemp()
        try:
            with os.fdopen(tmpfd, "w", encoding="utf-8") as f:
                f.writelines(f"file '{p}'\n" for p in self.source)
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
            stderr_write(f"{e}\n")
            try:
                os.unlink(self.output)
            except FileNotFoundError:
                pass
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
                stderr_write(f"{e}\n")
            else:
                stderr_write(f"Remove: {file}\n")


def find_video_groups(root):
    # ffmpeg requires absolute path
    stack = [op.abspath(root)]
    seen = set()
    groups = defaultdict(dict)
    matcher = re.compile(
        r"""
        (?P<pre>.+?)
        (?P<sep>[\s._-]+(?:part|chunk|vol|cd|dvd)?[\s._-]*)
        (?P<num>0?[1-9]|[1-9][0-9]|[a-z])\s*
        (?P<ext>\.(?:mp4|wmv|avi|m[ko4]v))
        """,
        flags=re.VERBOSE | re.IGNORECASE,
    ).fullmatch

    while stack:
        root = stack.pop()
        seen.clear()
        groups.clear()

        try:
            with os.scandir(root) as it:
                for entry in it:
                    name = entry.name
                    seen.add(name)
                    if entry.is_dir(follow_symlinks=False):
                        if name[0] not in "#@":
                            stack.append(entry.path)
                    else:
                        m = matcher(name)
                        if not m:
                            continue
                        n = m["num"]
                        is_digit = n.isdigit()
                        # if n is a-z, convert to 1-26
                        n = int(n) if is_digit else ord(n.lower()) - 96
                        groups[
                            (
                                m["pre"],
                                m["ext"].lower(),
                                m["sep"],
                                is_digit,
                            )
                        ][n] = entry.path

        except OSError as e:
            stderr_write(f"{e}\n")
            continue

        for k, v in groups.items():
            n = len(v)
            if 1 < n == max(v):
                name = k[0] + k[1]
                if name in seen:
                    continue
                yield VideoGroup(
                    source=tuple(v[i] for i in range(1, n + 1)),
                    output=op.join(root, name),
                )


if os.name == "posix":
    ffmpeg = "ffmpeg"
    ffprobe = "ffprobe"
else:
    ffmpeg = "ffmpeg.exe"
    ffprobe = "ffprobe.exe"


def _find_ffmpeg(args_ffmpeg):
    global ffmpeg, ffprobe

    if args_ffmpeg:
        if op.isdir(args_ffmpeg):
            ffmpeg = op.join(args_ffmpeg, ffmpeg)
            ffprobe = op.join(args_ffmpeg, ffprobe)
        else:
            ffmpeg = args_ffmpeg
            ffprobe = op.join(op.dirname(args_ffmpeg), ffprobe)

    for exe in ffmpeg, ffprobe:
        if not shutil.which(exe):
            stderr_write(
                f"Error: {exe} not found. Please be sure it can be "
                "found in $PATH or the directory passed via '-f' option.\n"
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
        f"{Sep.BOLD}\n"
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
            f"{Sep.BOLD}\n"
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
    for group in find_video_groups(args.source):
        group.print()
        results.add(group)

    stderr_write(
        "{}\nScan finished, {} files can be concatenated into {} files.\n".format(
            Sep.BOLD, sum(len(v.source) for v in results), len(results)
        )
    )
    if not results:
        stderr_write("No change can be made.\n")
        return

    if not args.quiet:
        results = set(user_filter(results, "Apply concatenations?", False))

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
