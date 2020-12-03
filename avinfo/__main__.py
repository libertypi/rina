import argparse
import sys
from pathlib import Path

from avinfo import common


def parse_args():
    def target_func(target: str):

        path = Path(target)
        if path.exists():
            return path

        if target == path.name == path.stem:
            return target

        raise argparse.ArgumentTypeError(f"Invalid target: '{target}'")

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
        help="detect publish ID, title and publish date from videos",
    )
    group.add_argument(
        "-a",
        "--actress",
        dest="mode",
        action="store_const",
        const="actress",
        help="detect actress name and birth from directories",
    )
    group.add_argument(
        "-d",
        "--dir",
        dest="mode",
        action="store_const",
        const="dir",
        help="modify directories' mtime to the newest file inside",
    )
    group.set_defaults(mode="video")

    parser.add_argument(
        "-q",
        "--quiet",
        dest="quiet",
        action="store_true",
        help="apply changes without prompting. (default: %(default)s)",
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

    if args.mode == "dir" and target_type != "dir":
        parser.error(f"When mode is '{args.mode}', the target must be a directory.")
    elif args.mode == "actress" and target_type == "file":
        parser.error(f"When mode is '{args.mode}', the target must be a directory or a keyword.")

    return args, target_type


def print_banner():
    print(common.sepSlim)
    for m in ("Adult Video Information Detector", "By David Pi"):
        print(m.center(common.sepWidth))
    print(common.sepSlim)


def process_scan_results(total: int, changed: list, failed: list, mode: str, quiet: bool):

    total_changed = len(changed)
    print(common.sepBold)
    print(f"{mode} scan finished.")

    msg = f"Total: {total}. Changed: {total_changed}. Failed: {len(failed)}."
    if not total_changed:
        print(msg)
        print("No change can be made.")
        return

    msg = f"""{msg}
Please choose an option:
1) apply changes
2) reload changes
3) reload failures
4) quit
"""

    while not quiet:
        choice = input(msg)

        if choice == "1":
            break
        elif choice == "4":
            sys.exit()

        print(common.sepBold)
        if choice == "2":
            for obj in changed:
                obj.print()
        elif choice == "3":
            for obj in failed:
                obj.print()
        else:
            print("Invalid option.")
        print(common.sepBold)

    failed.clear()
    sep = common.sepSlim + "\n"
    printProgressBar = common.printProgressBar

    print("Applying changes...")
    printProgressBar(0, total_changed)

    with open(common.logFile, "a", encoding="utf-8") as f:
        for i, obj in enumerate(changed, 1):
            try:
                obj.apply()
            except OSError as e:
                failed.append((obj.path, e))
            else:
                f.write(f"[{common.now()}] Mode: {mode}\n")
                f.write(obj.report)
                f.write(sep)
            printProgressBar(i, total_changed)

    for path, e in failed:
        common.color_printer("Target:", path, color="red")
        common.color_printer("Error:", e, color="red")


def main():
    print_banner()

    args, target_type = parse_args()
    target = args.target
    mode = args.mode

    print(f"Target: {args.target}. Mode: {mode}")
    print("Task start...")

    if mode == "actress":
        from avinfo import actress

        if target_type == "str":
            actress.Actress(target).print()
        else:
            process_scan_results(
                *actress.scan_path(target),
                mode=mode,
                quiet=args.quiet,
            )
    else:
        from avinfo import video

        if target_type == "str":
            video.AVString(target).print()
        elif mode == "video":
            process_scan_results(
                *video.scan_path(target, target_type == "dir"),
                mode=mode,
                quiet=args.quiet,
            )
        if target_type == "dir":
            video.update_dir_mtime(target)


if __name__ == "__main__":
    main()
