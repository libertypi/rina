import os
import os.path as op
import re
import subprocess
import warnings
from collections import defaultdict
from shutil import which
from tempfile import mkstemp
from textwrap import dedent

from avinfo._utils import SEP_BOLD, SEP_SLIM, get_choice_as_int

FFMPEG = "ffmpeg"


class ConcatVideo:

    __slots__ = ("output_path", "input_files", "report", "applied")

    def __init__(self, output_path: str, input_files: tuple) -> None:

        self.output_path = output_path
        self.input_files = input_files
        self.applied = False

        self.report = "files ({}):\n  {}\noutput preview:\n  {}".format(
            len(input_files),
            "\n  ".join(input_files),
            output_path,
        )

    def apply(self):

        if self.applied:
            warnings.warn("alreadly applied")
            return

        tmpfd, tmpfile = mkstemp()
        try:
            with os.fdopen(tmpfd, "w", encoding="utf-8") as f:
                f.writelines(f"file '{p}'\n" for p in self.input_files)
            subprocess.run(
                (FFMPEG, "-f", "concat", "-safe", "0", "-i", tmpfile, "-c",
                 "copy", self.output_path),
                check=True,
            )
        except subprocess.CalledProcessError as e:
            warnings.warn(f"{FFMPEG} error: {e}")
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
                warnings.warn(f'removing "{file}" failed: {e}')
            else:
                print("remove:", file)


def find_consecutive_videos(root):

    # ffmpeg requires absolute path
    root = op.abspath(root)

    stack = [root]
    names = set()
    groups = defaultdict(dict)
    matcher = re.compile(
        r"""
        (?P<pre>.+?)
        (?P<sep>(?:[\s._-]+(?:part|chunk|vol|cd|dvd))?[\s._-]*)
        (?P<num>0*[1-9][0-9]*)\s*
        (?P<ext>\.(?:mp4|wmv|avi|m[ko4]v))
        """,
        flags=re.VERBOSE | re.IGNORECASE,
    ).fullmatch

    while stack:

        root = stack.pop()
        names.clear()
        groups.clear()

        try:
            with os.scandir(root) as it:

                for entry in it:

                    name = entry.name
                    if name[0] in "#@.":
                        continue
                    names.add(name)

                    if entry.is_dir(follow_symlinks=False):
                        stack.append(entry.path)
                    else:
                        m = matcher(name)
                        if m:
                            groups[(
                                m["pre"],
                                m["sep"],
                                m["ext"].lower(),
                            )][int(m["num"])] = entry.path

        except OSError as e:
            warnings.warn(f"error occurred scanning {root}: {e}")
            continue

        for k, v in groups.items():
            n = len(v)
            if 1 < n == max(v):

                name = k[0] + k[2]
                if name in names:
                    continue

                yield ConcatVideo(
                    op.join(root, name),
                    tuple(v[i] for i in range(1, n + 1)),
                )


def main(top_dir, quiet: bool = False):

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
        ))

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
                please select what to do with following ({{}} of {len(result)}):
                {SEP_SLIM}
                {{}}
                {SEP_SLIM}
                1) select
                2) skip
                3) quit
            """
            msg = dedent(msg)

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
        video.apply()

    if not quiet:
        msg = f"""\
        {SEP_BOLD}
        delete all the successfully converted input files?
        please check with caution.
        1) yes
        2) no
        """
        choice = get_choice_as_int(dedent(msg), 2)
        if choice == 1:
            for video in result:
                video.remove_inputs()
