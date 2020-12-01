import argparse
from pathlib import Path
from avinfo import actress, common, files


def parse_args():
    def file_or_kw(target: str):

        path = Path(target)
        if path.exists():
            return path

        if target == path.name == path.stem:
            return target

        raise argparse.ArgumentTypeError(f"Invalid target: '{target}'")

    parser = argparse.ArgumentParser(
        prog="avinfo",
        description="""Detect publish ID, title and date for Japanese adult videos.
Detect name and birthday for Japanese adult video stars.""",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-m",
        "--mode",
        dest="mode",
        action="store",
        choices=("f", "a", "d"),
        default="f",
        help="""Operation mode. (default: %(default)s)
f:  Detect publish ID, title and date for videos. 
a:  Detect dir name based on actress name.
d:  Modify directories' mtime base on their content.""",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        dest="quiet",
        action="store_true",
        help="Apply changes without prompting. (default: %(default)s)",
    )
    parser.add_argument(
        "target",
        type=file_or_kw,
        help="""The target, be it a file, a directory, or a keyword.
When mode d is selected, the target must be a directory.""",
    )

    args = parser.parse_args()

    if args.mode == "d" and not (isinstance(args.target, Path) and args.target.is_dir()):
        parser.error(f"When '--mode {args.mode}' is selected, the target must be a directory.")

    return args


def printBanner():
    msg = ("Adult Video Information Detector", "By David Pi")
    print(common.sepSlim)
    for m in msg:
        print(m.center(common.sepWidth))
    print(common.sepSlim)


def printTaskStart(args: argparse.Namespace):
    modes = {"a": "Actress", "f": "File", "d": "Directory"}
    print(f"Target: {args.target}. Mode: {modes[args.mode]}")
    print("Task start...")


def main():
    printBanner()

    args = parse_args()
    target = args.target

    printTaskStart(args)

    if args.mode == "a":
        actress.main(target, quiet=args.quiet)

    elif args.mode == "f":
        if isinstance(target, Path):
            files.handle_files(target, args.quiet)
            files.handle_dirs(target)
        else:
            files.AVString(target).scrape()

    else:
        files.handle_dirs(target)


if __name__ == "__main__":
    main()
