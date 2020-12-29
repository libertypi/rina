import argparse
import sys
from pathlib import Path
from textwrap import dedent

from avinfo._utils import color_printer, get_choice_as_int, sep_bold, sep_slim, sep_width


def parse_args():
    def target_func(target: str):

        path = Path(target)
        if path.exists():
            return path

        if target == path.name:
            return target

        raise argparse.ArgumentTypeError(f'"{target}" is unreachable')

    parser = argparse.ArgumentParser(
        prog="avinfo",
        description="""The ultimate AV detector.""",
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-v",
        "--video",
        dest="mode",
        action="store_const",
        const="video",
        help="detect information from videos (default)",
    )
    group.add_argument(
        "-a",
        "--actress",
        dest="mode",
        action="store_const",
        const="actress",
        help="detect actress bio from directories",
    )
    group.add_argument(
        "-c",
        "--concat",
        dest="mode",
        action="store_const",
        const="concat",
        help="find and concatenate consecutive videos",
    )
    group.add_argument(
        "-d",
        "--dir",
        dest="mode",
        action="store_const",
        const="dir",
        help="modify directories' mtime to the newest file inside",
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
        type=target_func,
        help="the target, be it a file, a directory, or a keyword",
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
        parser.error(f"When mode is '{args.mode}', the target must be a directory or a keyword.")

    elif args.mode in ("concat", "dir") and target_type != "dir":
        parser.error(f"When mode is '{args.mode}', the target must be a directory.")

    return args, target_type


def printProgressBar(iteration, total, prefix="Progress", suffix="Complete", length=sep_width, fill="█"):
    percent = f"{100 * (iteration / float(total)):.1f}"
    filledLength = int(length * iteration // total)
    bar = f'{fill * filledLength}{"-" * (length - filledLength)}'
    print(f"\r{prefix} |{bar}| {percent}% {suffix}", end="\r")
    if iteration == total:
        print()


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
    print(sep_bold)
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
            {sep_bold}
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

    print(f"{sep_bold}\nApplying changes...")
    printProgressBar(0, total_changed)

    failed.clear()
    for i, obj in enumerate(changed, 1):
        try:
            obj.apply()
        except OSError as e:
            failed.append((obj.path, e))
        printProgressBar(i, total_changed)

    for path, e in failed:
        color_printer("Target:", path, color="red")
        color_printer("Error:", e, color="red")


def main():

    print(sep_slim)
    for k in ("Adult Video Information Detector", "By David Pi"):
        print(k.center(sep_width))
    print(sep_slim)

    args, target_type = parse_args()
    target = args.target
    mode = args.mode

    for k, v in ("target:", target), ("type:", target_type), ("mode:", mode):
        print(k, v)
    print(sep_bold)

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
