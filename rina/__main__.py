import dataclasses
import getpass
import json
import sys

from . import config_logger
from .arguments import parse_args
from .utils import (
    SEP_BOLD,
    SEP_SLIM,
    SEP_WIDTH,
    Settings,
    Status,
    config_file,
    get_choice_as_int,
    get_config,
    stderr_write,
    strftime,
)

_SECRET_SUFFIXES = ("_api", "_pass")


def _mask_secret(name: str, value: str | None) -> str:
    """Mask values for fields whose names look secret-bearing."""
    if not value:
        return "(not set)"
    if name.endswith(_SECRET_SUFFIXES):
        return "********"
    return value


def cmd_set(args) -> None:
    """Get or set configuration values. See `rina set -h` for usage."""
    config = dataclasses.asdict(get_config())

    # No name: list all fields (masked).
    if args.name is None:
        kw = max(map(len, config))
        for k, v in config.items():
            stderr_write(f"{k:<{kw}} : {_mask_secret(k, v)}\n")
        return

    names = (args.name,)
    if args.value is None and args.name in (
        "nordvpn",
        "nordvpn_user",
    ):
        n = args.name.partition("_")[0]
        names = (n + "_user", n + "_pass")

    changed = []
    for n in names:
        try:
            old = config[n]
        except KeyError:
            sys.exit(f"Unknown config field: {n!r}. Valid: {list(config)}")
        if args.value is None:
            reader = getpass.getpass if n.endswith(_SECRET_SUFFIXES) else input
            new = reader(f"{n} [{_mask_secret(n, old)}]: ").strip() or None
        else:
            # Treat an empty CLI value as a clear, mirroring interactive mode.
            new = args.value or None
        if new != old:
            config[n] = new
            changed.append(n)

    if not changed:
        stderr_write("No changes.\n")
        return

    config_file.parent.mkdir(parents=True, exist_ok=True)
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    stderr_write(f"Updated: {', '.join(changed)}\n")


def _print_banner(args):
    """Print the program header with command details."""
    stderr_write(
        f"{SEP_BOLD}\n"
        f'{"Rina: The All-in-One AV Toolbox":^{SEP_WIDTH}}\n'
        f"{SEP_SLIM}\n"
    )
    config = {"command": None}
    include = ("recursive",)
    config.update({k: v for k, v in vars(args).items() if v or k in include})
    kl = max(map(len, config))
    for k, v in config.items():
        # format certain types
        if isinstance(v, float):
            v = strftime(v)
        elif isinstance(v, (range, list)):
            v = ", ".join(map(str, v))
        stderr_write(f"{k.title():>{kl}}: {v}\n")
    stderr_write(f"{SEP_BOLD}\n")


def process_stream(stream):
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
        f"Scan finished.\nTotal: {total}. Changed: {len(changed)}. Failure: {len(failure)}.\n"
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
    Settings.DRYRUN = args.dryrun
    Settings.YES = args.yes
    Settings.PROXY = args.proxy
    config_logger(args.verbose)

    if args.command == "set":
        cmd_set(args)
        return

    _print_banner(args)

    if args.command == "video":
        from . import files, video

        if args.type == "keyword":
            video.from_string(args.source).print()
            return

        process_stream(video.from_args(args))
        if args.type == "dir":
            files.update_dir_mtime(args.source)

    elif args.command == "western":
        from . import files, western

        process_stream(western.from_args(args))
        if args.type == "dir":
            files.update_dir_mtime(args.source)

    elif args.command == "idol":
        from . import idol

        if args.type == "keyword":
            idol.Idol(args.source).print()
        else:
            process_stream(idol.from_args(args))

    elif args.command == "birth":
        from . import birth

        birth.main(args)

    elif args.command == "touch":
        from . import files

        files.update_dir_mtime(args.source)

    elif args.command == "concat":
        from . import concat

        concat.main(args)

    else:
        raise ValueError(args.command)


if __name__ == "__main__":
    main()
