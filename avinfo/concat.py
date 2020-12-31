import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from shutil import which
from tempfile import mkstemp
from textwrap import dedent
from typing import Tuple

from avinfo._utils import SEP_BOLD, SEP_SLIM, get_choice_as_int

FFMPEG = "ffmpeg"


class ConcatVideo:

    __slots__ = ("output_path", "input_files", "report")

    def __init__(self, output_path: Path, input_files: Tuple[Path]) -> None:
        self.output_path = output_path
        self.input_files = input_files
        self.report = "files ({}):\n{}\noutput preview:\n  {}".format(
            len(input_files),
            "\n".join(f"  {p}" for p in input_files),
            output_path,
        )

    def apply(self):
        tmpfd, tmpfile = mkstemp()
        try:
            with os.fdopen(tmpfd, "w", encoding="utf-8") as f:
                f.writelines(f"file '{p}'\n" for p in self.input_files)
            subprocess.run(
                (
                    FFMPEG,
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    tmpfile,
                    "-c",
                    "copy",
                    self.output_path,
                )
            )
        finally:
            os.unlink(tmpfile)


def find_consecutive_videos(top_dir: Path):

    try:
        top_dir = top_dir.resolve()
    except AttributeError:
        top_dir = Path(top_dir).resolve()

    file_set = set()
    groups = defaultdict(dict)
    matcher = re.compile(
        r"""
        (?P<pre>.+?)
        (?P<sep>(?:[\s._-]+(?:chunk|vol|cd|dvd))?[\s._-]*)
        (?P<num>0*[1-9][0-9]*)
        (?P<ext>\.(?:mp4|wmv|avi|mkv))
        """,
        flags=re.VERBOSE | re.IGNORECASE,
    ).fullmatch

    for root, _, files in os.walk(top_dir):

        for m in filter(None, map(matcher, files)):
            groups[(m["pre"], m["sep"], m["ext"].lower())][int(m["num"])] = m.string
        if not groups:
            continue

        joinpath = Path(root).joinpath

        for k, v in groups.items():

            n = len(v)
            if 1 < n == max(v):
                output_name = k[0] + k[2]

                if not file_set:
                    file_set.update(files)
                if output_name in file_set:
                    continue

                yield ConcatVideo(
                    output_path=joinpath(output_name),
                    input_files=tuple(joinpath(v[i]) for i in range(1, n + 1)),
                )

        file_set.clear()
        groups.clear()


def main(top_dir: Path, quiet: bool = False):

    if which(FFMPEG) is None:
        print(f"{FFMPEG} not found.")
        return

    result = []
    for video in find_consecutive_videos(top_dir):
        result.append(video)
        print(SEP_SLIM)
        print(video.report)

    if not result:
        print("No change can be made.")
        return

    print(
        "{}\nScan finished, {} files can be concatenated into {} files.".format(
            SEP_BOLD,
            sum(len(v.input_files) for v in result),
            len(result),
        )
    )

    if not quiet:
        msg = f"""\
            {SEP_BOLD}
            please choose an option:
            1) apply all
            2) select items
            3) quit
        """
        choice = get_choice_as_int(dedent(msg), 3)

        if choice == 2:
            msg = f"""\
                {SEP_BOLD}
                please select what to do with following files:
                {SEP_SLIM}
                {{}}
                {SEP_SLIM}
                1) select
                2) skip
                3) quit
            """
            msg = dedent(msg)

            for i, video in enumerate(result):
                choice = get_choice_as_int(msg.format(video.report), 3)
                if choice == 2:
                    result[i] = None
                elif choice == 3:
                    return

            result = filter(None, result)

        elif choice == 3:
            return

    for video in result:
        video.apply()
