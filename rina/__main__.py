import sys

from . import Config, set_logger
from .arguments import parse_args
from .utils import (
    SEP_BOLD,
    SEP_SLIM,
    SEP_WIDTH,
    Status,
    get_choice_as_int,
    stderr_write,
    strftime,
)


def _print_header(args):
    """Print the program header with command details."""
    stderr_write(
        f"{SEP_BOLD}\n"
        f'{"Rina: The All-in-One Japanese AV Toolbox":^{SEP_WIDTH}}\n'
        f"{SEP_SLIM}\n"
    )
    config = {"command": None, "source": None}
    config.update({k: v for k, v in vars(args).items() if v is not None})
    kl = max(map(len, config))
    for k, v in config.items():
        # format certain types
        if isinstance(v, float):
            v = strftime(v)
        elif isinstance(v, range):
            v = ", ".join(map(str, v))
        stderr_write(f"{k.title():>{kl}}: {v}\n")
    stderr_write(f"{SEP_BOLD}\n")


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

    if total:
        stderr_write(f"{SEP_BOLD}\n")
    stderr_write(
        f"{args.command.title()} scan finished.\n"
        f"Total: {total}. Changed: {len(changed)}. Failure: {len(failure)}.\n"
    )
    if not changed:
        stderr_write("No change can be made.\n")
        return

    msg = (
        f"{SEP_BOLD}\n"
        "Please choose an option:\n"
        f"1) apply changes ({len(changed)} items)\n"
        f"2) reload changes ({len(changed)} items)\n"
        f"3) reload failures ({len(failure)} items)\n"
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

    failure.clear()
    stderr_write(f"{SEP_BOLD}\nApplying changes...\n")
    for obj in progressbar(changed):
        try:
            obj.apply()
        except OSError as e:
            failure.append(e)
    for obj in failure:
        stderr_write(f"Failed to process file: {obj}\n")


def progressbar(sequence, width: int = SEP_WIDTH):
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

    set_logger(args.verbose)
    Config.DRYRUN = args.dryrun
    Config.YES = args.yes

    _print_header(args)

    if args.command == "video":
        from rina import files, video

        if args.type == "keyword":
            video.from_string(args.source).print()
        elif args.type == "dir":
            process_stream(video.from_args(args), args)
            files.update_dir_mtime(args.source)
        else:
            process_stream((video.from_path(args.source),), args)

    elif args.command == "idol":
        from rina import idol

        if args.type == "keyword":
            idol.Idol(args.source).print()
        else:
            process_stream(idol.from_args(args), args)

    elif args.command == "dir":
        from rina import files

        files.update_dir_mtime(args.source)

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
