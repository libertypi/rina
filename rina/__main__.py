import logging
import sys

from rina.arguments import parse_args
from rina.utils import (
    SEP_BOLD,
    SEP_SLIM,
    SEP_WIDTH,
    Status,
    get_choice_as_int,
    stderr_write,
)


def process_stream(stream, args):
    changed = []
    failure = []
    total = 0

    for obj in stream:
        total += 1
        obj.print()
        if obj.status == Status.UPDATED:
            changed.append(obj)
        elif obj.status == Status.FAILURE:
            failure.append(obj)

    stderr_write(f"{SEP_BOLD}\n{args.command.title()} scan finished.\n")

    msg = f"Total: {total}. Changed: {len(changed)}. Failure: {len(failure)}."
    if not changed:
        stderr_write(f"{msg}\nNo change can be made.\n")
        return

    if args.quiet:
        stderr_write(msg + "\n")
    else:
        msg = (
            f"{SEP_BOLD}\n"
            f"{msg}\n"
            "Please choose an option:\n"
            "1) apply changes\n"
            "2) reload changes\n"
            "3) reload failures\n"
            "4) quit\n"
        )
        while True:
            choice = get_choice_as_int(msg, 4)
            if choice == 1:
                break
            if choice == 4:
                sys.exit()
            for obj in changed if choice == 2 else failure:
                obj.print()

    stderr_write(f"{SEP_BOLD}\nApplying changes...\n")
    for obj in progress(changed):
        try:
            obj.apply()
        except OSError as e:
            logging.error(e)


def progress(sequence, width: int = SEP_WIDTH):
    """Make an iterator that returns values from the input sequence while
    printing a progress bar."""
    total = len(sequence)
    fmt = f"\rProgress |{{:-<{width}}}| {{:.1%}} Complete".format
    for i, obj in enumerate(sequence, 1):
        stderr_write(fmt("█" * (i * width // total), i / total))
        yield obj
    if total:
        stderr_write("\n")


def main():
    args = parse_args()

    stderr_write(
        f"{SEP_SLIM}\n"
        f'{"Adult Video Helper":^{SEP_WIDTH}}\n'
        f'{"By David Pi":^{SEP_WIDTH}}\n'
        f"{SEP_SLIM}\n"
        f"command: {args.command}, source: {args.source}\n"
        f"{SEP_BOLD}\n"
    )

    if args.command == "video":
        from rina import scandir, video

        if args.type == "keyword":
            video.from_string(args.source).print()
        elif args.type == "dir":
            process_stream(video.from_args(args), args)
            scandir.update_dir_mtime(args.source)
        else:
            process_stream((video.from_path(args.source),), args)

    elif args.command == "idol":
        from rina import idol

        if args.type == "keyword":
            idol.Idol(args.source).print()
        else:
            process_stream(idol.from_args(args), args)

    elif args.command == "dir":
        from rina import scandir

        scandir.update_dir_mtime(args.source)

    elif args.command == "concat":
        from rina import concat

        concat.main(args)

    elif args.command == "birth":
        from rina import birth

        birth.main(args)

    else:
        raise ValueError(args.command)


if __name__ == "__main__":
    main()
