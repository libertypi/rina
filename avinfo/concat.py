import os
import os.path as op
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict

from avinfo._utils import SEP_BOLD, SEP_SLIM, get_choice_as_int, stderr_write

FFMPEG = "ffmpeg"


class ConcatVideo:

    __slots__ = ("output_path", "input_files", "report", "applied")

    def __init__(self, output_path: str, input_files) -> None:

        self.output_path = output_path
        self.input_files = input_files = tuple(input_files)
        self.applied = False

        self.report = "files ({}):\n  {}\noutput:\n  {}".format(
            len(input_files),
            "\n  ".join(input_files),
            output_path,
        )

    def apply(self, ffmpeg: str = FFMPEG):

        if self.applied:
            return

        tmpfd, tmpfile = tempfile.mkstemp()
        try:
            with os.fdopen(tmpfd, "w", encoding="utf-8") as f:
                f.writelines(f"file '{p}'\n" for p in self.input_files)
            subprocess.run(
                (ffmpeg, "-f", "concat", "-safe", "0", "-i", tmpfile, "-c",
                 "copy", self.output_path),
                check=True,
            )
        except subprocess.CalledProcessError as e:
            stderr_write(f"{e}\n")
            try:
                os.unlink(self.output_path)
            except FileNotFoundError:
                pass
        else:
            self.applied = True
        finally:
            os.unlink(tmpfile)

    def remove_inputs(self):

        if not self.applied:
            return

        for file in self.input_files:
            try:
                os.unlink(file)
            except OSError as e:
                stderr_write(f"{e}\n")
            else:
                stderr_write(f"remove: {file}\n")


def find_consecutive_videos(root: Path):

    # ffmpeg requires absolute path
    stack = [op.abspath(root)]
    seen = set()
    groups = defaultdict(dict)
    matcher = re.compile(
        r"""
        (?P<pre>.+?)
        (?P<sep>[\s._-]+(?:part|chunk|vol|cd|dvd)?[\s._-]*)
        (?P<num>0*[1-9][0-9]*|[a-z])\s*
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
                        # if n is not a digit, convert a-z to 1-26
                        n = int(n) if is_digit else ord(n.lower()) - 96
                        groups[(
                            m["pre"],
                            m["ext"].lower(),
                            m["sep"],
                            is_digit,
                        )][n] = entry.path

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
                    op.join(root, name),
                    (v[i] for i in range(1, n + 1)),
                )


def main(args):

    ffmpeg = shutil.which(args.ffmpeg or FFMPEG)
    if ffmpeg is None:
        stderr_write("Error: ffmpeg not found. "
                     "Please make sure it is in PATH, "
                     "or passed via --ffmpeg argument.\n")
        return

    result = []
    for video in find_consecutive_videos(args.target):
        result.append(video)
        stderr_write(f"{SEP_SLIM}\n{video.report}\n")

    if not result:
        stderr_write("No change can be made.\n")
        return

    stderr_write(
        "{}\nScan finished, {} files can be concatenated into {} files.\n".
        format(SEP_BOLD, sum(len(v.input_files) for v in result), len(result)))

    if not args.quiet:
        msg = (f"{SEP_BOLD}\n"
               "please choose an option:\n"
               "1) apply all\n"
               "2) select items\n"
               "3) quit\n")
        choice = get_choice_as_int(msg, 3)

        if choice == 2:
            msg = (
                f"{SEP_BOLD}\n"
                f"please select what to do with following ({{}} of {len(result)}):\n"
                f"{SEP_SLIM}\n"
                "{}\n"
                f"{SEP_SLIM}\n"
                "1) select\n"
                "2) skip\n"
                "3) quit\n")

            for i, video in enumerate(result):
                choice = get_choice_as_int(msg.format(i + 1, video.report), 3)
                if choice == 2:
                    result[i] = None
                elif choice == 3:
                    return
            result[:] = filter(None, result)

        elif choice == 3:
            return

    for video in result:
        video.apply(ffmpeg)

    if not args.quiet:
        msg = (f"{SEP_BOLD}\n"
               "delete all the successfully converted input files?\n"
               "please check with caution.\n"
               "1) yes\n"
               "2) no\n")
        choice = get_choice_as_int(msg, 2)
        if choice == 1:
            for video in result:
                video.remove_inputs()
