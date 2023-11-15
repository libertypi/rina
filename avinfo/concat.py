import os
import os.path as op
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict

from avinfo.utils import SEP_BOLD, SEP_SLIM, get_choice_as_int, stderr_write

if os.name == "posix":
    ffmpeg = "ffmpeg"
    ffprobe = "ffprobe"
else:
    ffmpeg = "ffmpeg.exe"
    ffprobe = "ffprobe.exe"


class ConcatVideo:
    __slots__ = ("output", "input", "report", "applied")

    def __init__(self, output: str, input: tuple) -> None:
        self.output = output
        self.input = input
        self.applied = False

        self.report = "input ({}):\n  {}\noutput:\n  {}\n{}\n".format(
            len(input), "\n  ".join(input), output, SEP_SLIM
        )

    def has_diff_streams(self):
        """compare streams in input files. return True if there is
        difference, and write some message to stderr."""
        first = msg = None
        try:
            for file in self.input:
                o = subprocess.run(
                    (
                        ffprobe,
                        "-loglevel",
                        "0",
                        "-show_entries",
                        "stream=index,codec_name,width,height,time_base",
                        "-print_format",
                        "compact",
                        file,
                    ),
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout
                if first is None:
                    first = o
                elif first != o:
                    msg = f"stream difference:\n{self.input[0]}:\n{first}{SEP_SLIM}\n{file}:\n{o}"
                    break
            else:
                return False
        except subprocess.CalledProcessError as msg:
            msg = f"{msg}\n"
        stderr_write(
            f"{SEP_BOLD}\nerror occured when verifying input files:\n"
            f"{self.report}{msg}{SEP_SLIM}\n"
        )
        return True

    def concat(self):
        tmpfd, tmpfile = tempfile.mkstemp()
        try:
            with os.fdopen(tmpfd, "w", encoding="utf-8") as f:
                f.writelines(f"file '{p}'\n" for p in self.input)
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

    def remove_inputs(self):
        if not self.applied:
            return

        for file in self.input:
            try:
                os.unlink(file)
            except OSError as e:
                stderr_write(f"{e}\n")
            else:
                stderr_write(f"remove: {file}\n")


def find_consecutive_videos(root):
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
                yield ConcatVideo(
                    op.join(root, name), tuple(v[i] for i in range(1, n + 1))
                )


def main(args):
    global ffmpeg, ffprobe

    if args.ffmpeg:
        if op.isdir(args.ffmpeg):
            ffmpeg = op.join(args.ffmpeg, ffmpeg)
            ffprobe = op.join(args.ffmpeg, ffprobe)
        else:
            ffmpeg = args.ffmpeg
            ffprobe = op.join(op.dirname(args.ffmpeg), ffprobe)
    for i in ffmpeg, ffprobe:
        if not shutil.which(i):
            stderr_write(
                f"Error: {i} not found. Please be sure ffmpeg can be "
                "found in $PATH or the directory passed via '-f' option.\n"
            )
            return

    result = []
    for video in find_consecutive_videos(args.target):
        result.append(video)
        stderr_write(video.report)

    if not result:
        stderr_write("No change can be made.\n")
        return

    stderr_write(
        "{}\nScan finished, {} files can be concatenated into {} files.\n".format(
            SEP_BOLD, sum(len(v.input) for v in result), len(result)
        )
    )

    if not args.quiet:
        msg = (
            f"{SEP_BOLD}\n"
            "please choose an option:\n"
            "1) apply all\n"
            "2) select items\n"
            "3) quit\n"
        )
        choice = get_choice_as_int(msg, 3)

        if choice == 2:
            msg = (
                f"{SEP_BOLD}\n"
                f"please select what to do with following ({{}} of {len(result)}):\n"
                f"{SEP_SLIM}\n"
                "{}"
                "1) select\n"
                "2) skip\n"
                "3) quit\n"
            )

            for i, video in enumerate(result):
                choice = get_choice_as_int(msg.format(i + 1, video.report), 3)
                if choice == 2:
                    result[i] = None
                elif choice == 3:
                    return
            result[:] = filter(None, result)

        elif choice == 3:
            return

    to_all = True if args.quiet else False  # skip all
    for video in result:
        if video.has_diff_streams():
            if to_all:
                choice = 3
            else:
                msg = (
                    "concat these files anyway (not recommended)?\n"
                    f"{SEP_SLIM}\n1) yes\n2) no (skip)\n3) skip all\n4) quit\n"
                )
                choice = get_choice_as_int(msg, 4)
                if choice == 4:
                    return
                if choice == 3:
                    to_all = True
            if choice != 1:
                stderr_write("files skipped.\n")
                continue
        video.concat()

    if not args.quiet:
        to_all = False  # delete all
        for video in result:
            if not video.applied:
                continue
            if not to_all:
                msg = (
                    f"{SEP_BOLD}\ndelete all input files?\n{video.report}"
                    "1) yes\n2) yes to all\n3) no\n4) quit\n"
                )
                choice = get_choice_as_int(msg, 4)
                if choice == 4:
                    return
                if choice == 3:
                    continue
                if choice == 2:
                    to_all = True
            video.remove_inputs()
