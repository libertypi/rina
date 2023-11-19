import argparse
import datetime
import re
from pathlib import Path

valid_types = {
    "video": ("dir", "file", "keyword"),
    "idol": ("dir", "keyword"),
    "concat": ("dir",),
    "dir": ("dir",),
}


def _add_source(parser, command):
    parser.add_argument(
        "source",
        help=f'the source. expect types: {", ".join(valid_types[command])}',
    )


def _add_filter(parser: argparse.ArgumentParser, recursive=True):
    r = parser.add_mutually_exclusive_group()
    r.add_argument(
        "-r",
        dest="recursive",
        action="store_true",
        help="search subdirectories recursively (default %(default)s)",
    )
    r.add_argument(
        "-R",
        dest="recursive",
        action="store_false",
        help="do not delve into subdirectories",
    )
    r.set_defaults(recursive=recursive)
    parser.add_argument(
        "-n",
        dest="newer",
        type=past_timestamp,
        help='include files newer than "n[DHMS]", e.g., "5D" for newer than 5 days\n'
        "Units: Days (D), Hours (H), Minutes (M), Seconds (S)\n",
    )
    parser.add_argument(
        "-i",
        "--include",
        dest="include",
        type=str,
        help="search only files that match the glob",
    )
    parser.add_argument(
        "-e",
        "--exclude",
        dest="exclude",
        type=str,
        help="skip files that match the glob",
    )
    parser.add_argument(
        "--exclude-dir",
        dest="exclude_dir",
        type=str,
        help="skip directories that match the glob",
    )


def _add_quiet(parser):
    parser.add_argument(
        "-q",
        dest="quiet",
        action="store_true",
        help="apply changes without prompting (default: %(default)s)",
    )


def parse_args():
    # main parser
    parser = argparse.ArgumentParser(
        description="Rina is an all-in-one Japanese AV toolbox.\n"
        "It searches online sources and processes local files.\n"
        "Type '%(prog)s <command> -h' for command-specific help.",
        epilog="Author: David Pi <libertypi@gmail.com>\n"
        "GitHub: <https://github.com/libertypi/rina>",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # sub-parsers
    subparsers = parser.add_subparsers(title="commands", dest="command", required=True)

    # video
    # source: dir, file, keyword
    command = "video"
    subparser = subparsers.add_parser(
        "video",
        help="scrape video information",
        description=(
            "Description:\n"
            "  Scrape video information from local directories, files, or keywords\n\n"
            "Examples:\n"
            "  Scrape all videos newer than 7 days in ~/dir:\n"
            "      %(prog)s -n 7D ~/dir\n"
            "  Scrape a single file and apply change without prompting:\n"
            "      %(prog)s -q heyzo-2288.mp4"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    _add_quiet(subparser)
    _add_source(subparser, command)
    _add_filter(subparser)

    # idol
    # source: dir, keyword
    command = "idol"
    subparser = subparsers.add_parser(
        "idol",
        help="search for idol biography",
        description=(
            "Description:\n"
            "  Search for idol biographies in local directories or by idol names\n\n"
            "Examples:\n"
            "  Search idols based on folder names under ~/dir:\n"
            "      %(prog)s ~/dir\n"
            "  Search for a specific actress:\n"
            "      %(prog)s 和登こころ"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    _add_quiet(subparser)
    _add_source(subparser, command)
    _add_filter(subparser, False)

    # concat
    # source: dir
    command = "concat"
    subparser = subparsers.add_parser(
        "concat",
        help="concatenate consecutive videos",
        description=(
            "Description:\n"
            "  Search and concatenate consecutive videos into a single file\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    subparser.add_argument(
        "-f",
        dest="ffmpeg",
        action="store",
        help="specify ffmpeg directory (searches $PATH if omitted)",
    )
    _add_quiet(subparser)
    _add_source(subparser, command)
    _add_filter(subparser)

    # dir
    # source: dir
    command = "dir"
    subparser = subparsers.add_parser(
        command,
        help="update directory timestamps",
        description=(
            "Description:\n"
            "  Update directory 'Modified Time' based on the newest file contained"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    _add_source(subparser, command)

    # birth
    command = "birth"
    subparser = subparsers.add_parser(
        "birth",
        help="search idols by birth year",
        description=(
            "Description:\n"
            "  Search for idols based on birth year and latest publications\n\n"
            "Examples:\n"
            "  Search for 1990-born idols active in the past year:\n"
            "    %(prog)s -a 365D 1990\n"
            "  Search for idols born between 1989-1991 with specific criteria:\n"
            "    %(prog)s -u -s -a 90D 1989-1991"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    subparser.add_argument(
        "-a",
        dest="active",
        action="store",
        default="365D",
        type=past_timestamp,
        help="active within specified timespan (default %(default)s)",
    )
    subparser.add_argument(
        "-u",
        dest="uncensored",
        action="store_true",
        help="filter for uncensored content (default %(default)s)",
    )
    subparser.add_argument(
        "-s",
        dest="solo",
        action="store_true",
        help="filter for solo performances (default %(default)s)",
    )
    subparser.add_argument(
        dest="source",
        action="store",
        type=year_range,
        help="specify year of birth (single year or range, e.g., 1989 or 1988-1991)",
    )

    args = parser.parse_args()

    # test source type
    # add args.type to Namespace
    if args.command in valid_types:
        source = Path(args.source)
        try:
            source = source.resolve(strict=True)
            args.type = "dir" if source.is_dir() else "file"
        except FileNotFoundError as e:
            if source.name != args.source:
                # a non-exist path
                parser.error(e)
            source = source.stem
            args.type = "keyword"
        except (OSError, RuntimeError) as e:
            parser.error(e)
        if args.type not in valid_types[args.command]:
            parser.error(
                "expect source to be a {}, not a {}.".format(
                    ", ".join(valid_types[args.command]), args.type
                )
            )
        args.source = source

    return args


def past_timestamp(date: str):
    """
    Converts a relative date string to a timestamp representing a past date and
    time. For example, an input of "5D" returns the timestamp of 5 days ago from
    now.
    """
    date = re.fullmatch(
        r"\s*(?:(?P<days>\d+)D)?"
        r"\s*(?:(?P<hours>\d+)H)?"
        r"\s*(?:(?P<minutes>\d+)[MT])?"
        r"\s*(?:(?P<seconds>\d+)S?)?\s*",
        date,
        re.IGNORECASE,
    )
    if date:
        date = {k: int(v) for k, v in date.groupdict(0).items()}
        try:
            if any(date.values()):
                return (
                    datetime.datetime.now() - datetime.timedelta(**date)
                ).timestamp()
        except (ValueError, OverflowError) as e:
            raise argparse.ArgumentTypeError(e)
    raise argparse.ArgumentError()


def year_range(years: str):
    """Convert `'1988-1990'` to `range(1988, 1991)`."""
    m = re.fullmatch(r"\s*(\d{4})(?:-(\d{4}))?\s*", years)
    if m:
        return range(int(m[1]), int(m[2] or m[1]) + 1)
    raise argparse.ArgumentError()