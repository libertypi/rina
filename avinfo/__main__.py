import argparse
import datetime
import re
import sys
from pathlib import Path

from avinfo._utils import (SEP_BOLD, SEP_SLIM, SEP_WIDTH, color_printer,
                           get_choice_as_int)


def parse_args():

    parser = argparse.ArgumentParser(
        description=("The Ultimate AV Detector\n"
                     "Author: David Pi <libertypi@gmail.com>"),
        epilog=
        ('examples:\n'
         '  %(prog)s -n 12H /mnt/dir     -> scrape all videos newer than 12 hours in "dir"\n'
         '  %(prog)s -a /mnt/dir         -> get actress bio from folder names under "dir"\n'
         '  %(prog)s -vq heyzo-2288.mp4  -> scrape a single file and apply change\n'
         '  %(prog)s 和登こころ          -> search for a particular actress'),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-v",
        "--video",
        dest="mode",
        action="store_const",
        const="video",
        help=("video mode: (target: dir, file, keyword)\n"
              "scrape video information"),
    )
    group.add_argument(
        "-a",
        "--actress",
        dest="mode",
        action="store_const",
        const="actress",
        help=("actress mode: (target: dir, keyword)\n"
              "search for actress biography"),
    )
    group.add_argument(
        "-c",
        "--concat",
        dest="mode",
        action="store_const",
        const="concat",
        help=("concat mode: (target: dir)\n"
              "recursively find and concatenate consecutive videos"),
    )
    group.add_argument(
        "-d",
        "--dir",
        dest="mode",
        action="store_const",
        const="dir",
        help=("dir mode: (target: dir)\n"
              "update dir mtime to the newest file inside"),
    )

    parser.add_argument(
        "-n",
        dest="newer",
        action="store",
        nargs="?",
        const="1D",
        type=parse_date,
        help=("for video and actress mode, only scan files new than the time.\n"
              "value: seconds (86400) or date string (1D2H3M4S) (default: 1D)"),
    )
    parser.add_argument(
        "--ffmpeg",
        dest="ffmpeg",
        action="store",
        help=("for concat mode, "
              "the path to ffmpeg executable (default: search PATH)"),
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
        type=normalize_target,
        help=("the target, be it a directory, a file, "
              "or a keyword (mode-dependent)"),
    )

    args = parser.parse_args()

    if isinstance(args.target, str):
        target_type = "keyword"
    elif args.target.is_dir():
        target_type = "dir"
    else:
        target_type = "file"

    if not args.mode:
        if target_type == "keyword" and not any(map(str.isascii, args.target)):
            args.mode = "actress"
        else:
            args.mode = "video"

    elif args.mode == "actress" and target_type == "file":
        parser.error(
            f"in {args.mode} mode, the target should be a dir or a keyword.")

    elif args.mode in ("concat", "dir") and target_type != "dir":
        parser.error(f"in {args.mode} mode, the target should be a directory.")

    return args, target_type


def normalize_target(target: str):

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


def parse_date(date: str):

    date = re.fullmatch(
        r"\s*(?:(?P<days>\d+)D)?"
        r"\s*(?:(?P<hours>\d+)H)?"
        r"\s*(?:(?P<minutes>\d+)[MT])?"
        r"\s*(?:(?P<seconds>\d+)S?)?\s*", date, re.IGNORECASE)
    if date:
        date = {k: int(v) for k, v in date.groupdict(0).items()}
        try:
            if any(date.values()):
                return (datetime.datetime.now() -
                        datetime.timedelta(**date)).timestamp()
        except (ValueError, OverflowError) as e:
            raise argparse.ArgumentTypeError(e)
    raise argparse.ArgumentError()


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

    print(f"{SEP_BOLD}\n{mode} scan finished.")

    msg = f"Total: {total}. Changed: {len(changed)}. Failed: {len(failed)}."
    if not changed:
        print(msg)
        print("No change can be made.")
        return

    if quiet:
        print(msg)
    else:
        msg = (f"{SEP_BOLD}\n"
               f"{msg}\n"
               "Please choose an option:\n"
               "1) apply changes\n"
               "2) reload changes\n"
               "3) reload failures\n"
               "4) quit\n")
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
    for obj in progress(changed):
        try:
            obj.apply()
        except OSError as e:
            failed.append((obj.path, e))

    for path, e in failed:
        color_printer("Target:", path)
        color_printer("Error:", e)


def progress(sequence, width: int = SEP_WIDTH):
    '''Make an iterator that returns values from the input sequence while
    printing a progress bar.'''
    total = len(sequence)
    if not total:
        return
    write = sys.stdout.write
    fmt = f"Progress |{{:-<{width}}}| {{:.1%}} Complete\r".format
    for i, obj in enumerate(sequence, 1):
        write(fmt("█" * (i * width // total), i / total))
        yield obj
    write("\n")


def main():

    args, target_type = parse_args()
    target = args.target
    mode = args.mode

    print(f"{SEP_SLIM}\n"
          f'{"Adult Video Information Detector":^{SEP_WIDTH}}\n'
          f'{"By David Pi":^{SEP_WIDTH}}\n'
          f"{SEP_SLIM}\n"
          f"target: {target}\n"
          f"type: {target_type}, mode: {mode}\n"
          f"{SEP_BOLD}\n"
          "Task start...")

    if mode == "actress":
        from avinfo import actress

        if target_type == "keyword":
            actress.Actress(target).print()
        else:
            process_scan(
                actress.scan_dir(target, args.newer),
                mode=mode,
                quiet=args.quiet,
            )

    elif mode == "concat":
        from avinfo import concat

        concat.main(target, ffmpeg=args.ffmpeg, quiet=args.quiet)

    else:
        from avinfo import video

        if target_type == "keyword":
            video.from_string(target).print()
            return

        if mode == "video":

            if target_type == "dir":
                scan = video.scan_dir(target, args.newer)
            else:
                scan = (video.from_path(target),)

            process_scan(scan, mode=mode, quiet=args.quiet)

        if target_type == "dir":
            video.update_dir_mtime(target)


if __name__ == "__main__":
    main()
