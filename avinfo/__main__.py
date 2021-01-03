import argparse
import sys
from pathlib import Path
from textwrap import dedent

from avinfo._utils import (SEP_BOLD, SEP_SLIM, SEP_WIDTH, color_printer,
                           get_choice_as_int)


def parse_args():

    parser = argparse.ArgumentParser(
        prog="avinfo",
        description="The ultimate AV detector.",
        epilog=dedent("""\
            examples:
              %(prog)s /mnt/dir           -> recursively scrape all videos in "dir"
              %(prog)s -a /mnt/dir        -> scan actress bio from folder names under "dir"
              %(prog)s -v heyzo-2288.mp4  -> scrape a single file
              %(prog)s 和登こころ         -> search for a particular actress
            """),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-v",
        "--video",
        dest="mode",
        action="store_const",
        const="video",
        help="scrape video info (target: dir, file, keyword)",
    )
    group.add_argument(
        "-a",
        "--actress",
        dest="mode",
        action="store_const",
        const="actress",
        help="detect actress bio (target: dir, keyword)",
    )
    group.add_argument(
        "-c",
        "--concat",
        dest="mode",
        action="store_const",
        const="concat",
        help="find and concat consecutive videos (target: dir)",
    )
    group.add_argument(
        "-d",
        "--dir",
        dest="mode",
        action="store_const",
        const="dir",
        help="update dir's mtime to the newest file inside (target: dir)",
    )

    parser.add_argument(
        "-q",
        "--quiet",
        dest="quiet",
        action="store_true",
        help="apply changes without prompting (default: %(default)s)",
    )
    parser.add_argument(
        "target",
        type=_normalize_target,
        help="the target, be it a directory, a file, or a keyword",
    )

    args = parser.parse_args()

    if isinstance(args.target, str):
        target_type = "str"
    elif args.target.is_dir():
        target_type = "dir"
    else:
        target_type = "file"

    if not args.mode:
        if target_type == "str" and not any(map(str.isascii, args.target)):
            args.mode = "actress"
        else:
            args.mode = "video"

    elif args.mode == "actress" and target_type == "file":
        parser.error(
            f"in {args.mode} mode, the target should be a dir or a keyword.")

    elif args.mode in ("concat", "dir") and target_type != "dir":
        parser.error(f"in {args.mode} mode, the target should be a directory.")

    return args, target_type


def _normalize_target(target: str):

    if not target.strip():
        raise argparse.ArgumentTypeError("empty argument")

    path = Path(target)
    try:
        return path.resolve(strict=True)
    except FileNotFoundError as e:
        if path.name == target:
            return path.stem
        raise argparse.ArgumentTypeError(e)
    except (OSError, RuntimeError) as e:
        raise argparse.ArgumentTypeError(e)


def process_scan(scan, mode: str, quiet: bool):

    changed = []
    failed = []
    total = 0
    mode = mode.title()

    for obj in scan:
        total += 1
        obj.print()
        if obj.status == "changed":
            changed.append(obj)
        elif obj.status == "failed":
            failed.append(obj)

    total_changed = len(changed)
    print(SEP_BOLD)
    print(f"{mode} scan finished.")

    msg = f"Total: {total}. Changed: {total_changed}. Failed: {len(failed)}."
    if not total_changed:
        print(msg)
        print("No change can be made.")
        return

    if quiet:
        print(msg)
    else:
        msg = f"""\
            {SEP_BOLD}
            {msg}
            Please choose an option:
            1) apply changes
            2) reload changes
            3) reload failures
            4) quit
        """
        msg = dedent(msg)

        while True:
            choice = get_choice_as_int(msg, 4)
            if choice == 1:
                break
            if choice == 4:
                sys.exit()
            for obj in changed if choice == 2 else failed:
                obj.print()

    print(f"{SEP_BOLD}\nApplying changes...")

    failed.clear()
    bar = print_progressbar(total_changed)
    for obj in changed:
        try:
            obj.apply()
        except OSError as e:
            failed.append((obj.path, e))
        next(bar)

    for path, e in failed:
        color_printer("Target:", path)
        color_printer("Error:", e)


def print_progressbar(total: int, length: int = SEP_WIDTH, fill: str = "█"):

    bar = '\rProgress |{}{}| {:.1%} Complete'.format
    for i in range(1, total + 1):
        n = i * length // total
        print(bar(fill * n, "-" * (length - n), i / total), end="\r")
        if i == total:
            print()
        yield i


def main():

    print(SEP_SLIM)
    for k in ("Adult Video Information Detector", "By David Pi"):
        print(k.center(SEP_WIDTH))
    print(SEP_SLIM)

    args, target_type = parse_args()
    target = args.target
    mode = args.mode

    print("target:", target)
    print("type:", target_type)
    print("mode:", mode)
    print(SEP_BOLD)
    print("Task start...")

    if mode == "actress":
        from avinfo import actress

        if target_type == "str":
            actress.Actress(target).print()
        else:
            process_scan(
                actress.scan_dir(target),
                mode=mode,
                quiet=args.quiet,
            )

    elif mode == "concat":
        from avinfo import concat

        concat.main(target, quiet=args.quiet)

    else:
        from avinfo import video

        if target_type == "str":
            video.from_string(target).print()
            return

        if mode == "video":

            if target_type == "dir":
                scan = video.scan_dir(target)
            else:
                scan = (video.from_path(target),)

            process_scan(scan, mode=mode, quiet=args.quiet)

        if target_type == "dir":
            video.update_dir_mtime(target)


if __name__ == "__main__":
    main()
