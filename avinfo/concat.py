import os
import re
import subprocess
from collections import defaultdict, deque
from pathlib import Path
from shutil import which
from tempfile import mkstemp
from textwrap import dedent
from typing import Tuple

from avinfo._interact import get_choice_as_int, sep_bold, sep_slim

FFMPEG = "ffmpeg"


class ConcatVideo:

    __slots__ = ("output_path", "input_files", "_report")

    def __init__(self, output_path: Path, input_files: Tuple[Path]) -> None:
        self.output_path = output_path
        self.input_files = input_files
        self._report = "files ({}):\n{}\noutput preview:\n  {}".format(
            len(input_files),
            "\n".join(f"  {p}" for p in input_files),
            output_path,
        )

    def apply(self):
        tmpfd, tmpfile = mkstemp()
        try:
            with os.fdopen(tmpfd, "w", encoding="utf-8") as f:
                f.writelines(f"file '{p}'\n" for p in self.input_files)
            subprocess.run((FFMPEG, "-f", "concat", "-safe", "0", "-i", tmpfile, "-c", "copy", self.output_path))
        finally:
            os.unlink(tmpfile)

    def __str__(self):
        return self._report


def find_consecutive_videos(top_dir: Path):

    if not isinstance(top_dir, Path):
        top_dir = Path(top_dir)
    top_dir = top_dir.resolve()

    tmp = defaultdict(dict)
    matcher = re.compile(
        r"""
        (?P<pre>.+?)
        (?P<sep>(?:[\s._-]+(?:chunk|vol|cd|dvd))?[\s._-]*)
        (?P<num>0*[1-9][0-9]*)
        (?P<ext>\.(?:mp4|wmv|avi|mkv))
        """,
        flags=re.VERBOSE | re.IGNORECASE,
    ).fullmatch

    for root, _, input_files in os.walk(top_dir):

        for m in filter(None, map(matcher, input_files)):
            tmp[(m["pre"], m["sep"], m["ext"].lower())][int(m["num"])] = m.string
        if not tmp:
            continue

        joinpath = Path(root).joinpath
        for k, v in tmp.items():
            n = len(v)
            if 1 < n == max(v):
                output_path = joinpath(k[0] + k[2])
                if output_path.exists():
                    continue
                yield ConcatVideo(
                    output_path=output_path,
                    input_files=tuple(joinpath(v[i]) for i in range(1, n + 1)),
                )
        tmp.clear()


def main(top_dir: Path, quiet: bool = False):

    if which(FFMPEG) is None:
        print(f"{FFMPEG} not found.")
        return

    result = deque()
    for video in find_consecutive_videos(top_dir):
        result.append(video)
        print(sep_slim)
        print(video)

    if not result:
        print("No change can be made.")
        return

    print(
        "{}\nScan finished, {} files can be concatenated into {} files.".format(
            sep_bold,
            sum(len(v.input_files) for v in result),
            len(result),
        )
    )

    if not quiet:
        msg = f"""\
            {sep_bold}
            please choose an option:
            1) apply all
            2) select items
            3) quit
        """
        choice = get_choice_as_int(dedent(msg), 3)

        if choice == 2:
            msg = f"""\
                {sep_bold}
                please select what to do with following files:
                {sep_slim}
                {{}}
                {sep_slim}
                1) select
                2) skip
                3) quit
            """
            msg = dedent(msg)

            for _ in range(len(result)):
                video = result.popleft()
                choice = get_choice_as_int(msg.format(video), 3)
                if choice == 1:
                    result.append(video)
                elif choice == 3:
                    return

        elif choice == 3:
            return

    for video in result:
        video.apply()
