#!/usr/bin/env python3

import argparse
import os.path

from avinfo import actress, common, files


def parse_args():
    description = """Detect publish ID, title and date for Japanese adult videos.
Detect name and birthday for Japanese adult video stars."""

    help_mode = """Operation mode. (default: %(default)s)
f:  Detect publish ID, title and date for videos. 
a:  Detect dir name based on actress name.
d:  Modify directories' mtime base on their content."""

    help_quiet = "Apply changes without prompting. (default: %(default)s)"

    help_target = """The target, be it a file, a directory, or a keyword.
When mode d is selected, the target must be a directory."""

    def file_or_kw(searchTarget: str) -> tuple:
        try:
            if os.path.exists(searchTarget):
                searchTarget = os.path.abspath(searchTarget)
                if os.path.isdir(searchTarget):
                    targetType = "dir"
                else:
                    targetType = "file"
            elif searchTarget == os.path.basename(searchTarget):
                targetType = "keyword"
            else:
                raise ValueError("Invalid target")
            return searchTarget, targetType
        except Exception as e:
            raise argparse.ArgumentTypeError(f"{searchTarget} is unreachable. Error: {e}")

    parser = argparse.ArgumentParser(description=description, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "-m", "--mode", dest="mode", action="store", choices=("f", "a", "d"), default="f", help=help_mode
    )
    parser.add_argument("-q", "--quiet", dest="quiet", action="store_true", help=help_quiet)
    parser.add_argument("target", type=file_or_kw, help=help_target)

    args = parser.parse_args()

    if args.mode == "d" and args.target[1] != "dir":
        parser.error(f"When '--mode {args.mode}' is selected, the target must be a directory.")

    return args


def main():
    common.logFile = os.path.join(os.path.dirname(__file__), common.logFile)
    common.printBanner()

    args = parse_args()

    common.printTaskStart(args.target, args.mode)

    if args.mode == "a":
        actress.main(args.target, quiet=args.quiet)
    elif args.mode == "f":
        files.main(args.target, quiet=args.quiet)
    else:
        files.handle_dirs(args.target)


if __name__ == "__main__":
    main()
