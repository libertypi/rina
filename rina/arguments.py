import argparse
import datetime
import re
from pathlib import Path

CMD_TYPES = {
    "video": ("dir", "file", "keyword"),
    "idol": ("dir", "keyword"),
    "concat": ("dir",),
    "dir": ("dir",),
}


def _add_source(
    parser: argparse.ArgumentParser,
    command: str,
    add_filter: bool = True,
    recursive: bool = True,
):
    parser.add_argument(
        "source",
        help=f'the source. expect types: {", ".join(CMD_TYPES[command])}',
    )
    if not add_filter:
        return
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
        help='include files newer than "n[DHMS]", e.g., "5D" for 5 days\n'
        "Units: Days (D), Hours (H), Minutes (M), Seconds (S)",
    )
    parser.add_argument(
        "-i",
        dest="include",
        type=str,
        action="append",
        help="search only files that match the glob, can be repeated",
    )
    parser.add_argument(
        "-e",
        dest="exclude",
        type=str,
        action="append",
        help="skip files that match the glob, can be repeated",
    )
    parser.add_argument(
        "-x",
        dest="exclude_dir",
        type=str,
        action="append",
        help="skip directories that match the glob, can be repeated",
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
    # common options
    parser.add_argument(
        "-d",
        "--dryrun",
        action="store_true",
        help="simulate actions without making changes",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="make rina more talkative",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="automatically confirm all prompts",
    )
    # sub-parsers
    subparsers = parser.add_subparsers(title="commands", required=True)

    # video
    # source: dir, file, keyword
    command = "video"
    subparser = subparsers.add_parser(
        command,
        aliases="v",
        help="scrape video information",
        description=(
            "Description:\n"
            "  Scrape video information from local directories, files, or keywords"
        ),
        epilog=(
            "Examples:\n"
            "  Scrape a single file:\n"
            "      %(prog)s heyzo-2288.mp4\n"
            "  Scrape all videos newer than 7 days in ~/dir:\n"
            "      %(prog)s ~/dir -n 7D"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    subparser.set_defaults(command=command)
    _add_source(subparser, command)

    # idol
    # source: dir, keyword
    command = "idol"
    subparser = subparsers.add_parser(
        command,
        aliases="i",
        help="search for idol biography",
        description=(
            "Description:\n"
            "  Search for idol biographies in local directories or by idol names"
        ),
        epilog=(
            "Examples:\n"
            "  Search idols based on folder names under ~/dir:\n"
            "      %(prog)s ~/dir\n"
            "  Search for a specific actress:\n"
            "      %(prog)s 小柳結衣"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    subparser.set_defaults(command=command)
    _add_source(subparser, command, recursive=False)

    # concat
    # source: dir
    command = "concat"
    subparser = subparsers.add_parser(
        command,
        aliases="c",
        help="concatenate consecutive videos",
        description=(
            "Description:\n"
            "  Search and concatenate consecutive videos into a single file"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    subparser.set_defaults(command=command)
    subparser.add_argument(
        "-f",
        dest="ffmpeg",
        action="store",
        help="specify the ffmpeg directory (searches $PATH if omitted)",
    )
    _add_source(subparser, command)

    # dir
    # source: dir
    command = "dir"
    subparser = subparsers.add_parser(
        command,
        aliases="d",
        help="update directory timestamps",
        description=(
            "Description:\n"
            "  Update directory 'Modified Time' based on the newest file contained"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    subparser.set_defaults(command=command)
    _add_source(subparser, command, add_filter=False)

    # birth
    command = "birth"
    subparser = subparsers.add_parser(
        command,
        aliases="b",
        help="search idols by birth year",
        description=(
            "Description:\n"
            "  Search for idols based on birth year and latest publications"
        ),
        epilog=(
            "Examples:\n"
            "  Search for 1990-born idols active in the past year:\n"
            "    %(prog)s -a 365D 1990\n"
            "  Search for idols born between 1989-1991 with specific criteria:\n"
            "    %(prog)s -u -s -a 90D 1989-1991"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    subparser.set_defaults(command=command)
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
    if args.command in CMD_TYPES:
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
        if args.type not in CMD_TYPES[args.command]:
            parser.error(
                "expect source type to be '{}', not {}.".format(
                    ", ".join(CMD_TYPES[args.command]), args.type
                )
            )
        args.source = source

    return args


def past_timestamp(date: str) -> float:
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
            raise argparse.ArgumentError(message=e)
    raise argparse.ArgumentError()


def year_range(years: str) -> range:
    """Convert '1988-1990' or '89-90' to range(1988, 1991)."""

    def to_year(y: str) -> int:
        """Convert a two-digit or four-digit string to a four-digit year."""
        y = int(y)
        if y > 99:
            return y
        year = datetime.datetime.today().year
        century = year // 100 * 100
        return century - 100 + y if y > year % 100 else century + y

    m = re.fullmatch(r"\s*(\d\d|\d{4})(?:-(\d\d|\d{4}))?\s*", years)
    if not m:
        raise argparse.ArgumentError()
    start = to_year(m[1])
    return range(start, (to_year(m[2]) if m[2] else start) + 1)
