import argparse
import datetime
import re
from pathlib import Path


def parse_args():

    valid_types = {
        "video": {"dir", "file", "keyword"},
        "idol": {"dir", "keyword"},
        "concat": {"dir"},
        "dir": {"dir"}
    }

    def add_target(parser, command):
        parser.add_argument(
            "target",
            help=f'the target. expect: {", ".join(valid_types[command])}.')

    def add_newer(parser):
        parser.add_argument(
            "-n",
            dest="newer",
            action="store",
            nargs="?",
            const="1D",
            type=date_within,
            help=
            ("scan files newer than this timespan.\n"
             "NEWER: n[DHMS]: n units of time. If unit is omit, presume seconds. If NEWER if omit, presume 1 day."
             ))

    def add_quiet(parser):
        parser.add_argument(
            "-q",
            dest="quiet",
            action="store_true",
            help="apply changes without prompting (default: %(default)s)")

    # main parser
    parser = argparse.ArgumentParser(
        description=("The Ultimate AV Helper\n"
                     "Author: David Pi <libertypi@gmail.com>\n"
                     "Type '%(prog)s <command> -h' for more details."),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # sub-parsers
    subparsers = parser.add_subparsers(title="commands",
                                       dest="command",
                                       required=True)

    # video
    # target: dir, file, keyword
    command = "video"
    parser_video = subparsers.add_parser(
        command,
        help="scrape video information",
        description=("description:\n"
                     "  Scrape video information for:\n"
                     "  - Local directories.\n"
                     "  - Local file.\n"
                     "  - A virtual filename.\n\n"
                     "examples:\n"
                     "  - scrape all videos newer than 12 hours in ~/dir:\n"
                     "      %(prog)s -n 12H ~/dir\n"
                     "  - scrape a single file and apply change:\n"
                     "      %(prog)s -q heyzo-2288.mp4"),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    add_newer(parser_video)
    add_quiet(parser_video)
    add_target(parser_video, command)

    # idol
    # target: dir, keyword
    command = "idol"
    parser_idol = subparsers.add_parser(
        command,
        help="search for idol biography",
        description=(
            "description:\n"
            "  Search for idol biography for:\n"
            "  - Local directories.\n"
            "  - An idol name.\n\n"
            "examples:\n"
            "  - search idols based on all folder names under ~/dir:\n"
            "      %(prog)s ~/dir\n"
            "  - search for a single actress:\n"
            "      %(prog)s 和登こころ"),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    add_newer(parser_idol)
    add_quiet(parser_idol)
    add_target(parser_idol, command)

    # concat
    # target: dir
    command = "concat"
    parser_concat = subparsers.add_parser(
        command,
        help="concat consecutive videos",
        description=("description:\n"
                     "  Search and concat consecutive videos: "
                     "[file_1.mp4, file_2.mp4...] -> file.mp4"),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser_concat.add_argument(
        "-f",
        dest="ffmpeg",
        action="store",
        help="the ffmpeg directory. Search $PATH if omit.",
    )
    add_quiet(parser_concat)
    add_target(parser_concat, command)

    # dir
    # target: dir
    command = "dir"
    parser_dir = subparsers.add_parser(
        command,
        help=
        "updates the mtime of folders according the latest file stored in it",
        description=
        ("description:\n"
         "  Updates the 'Modified Time' of every folder according the latest "
         "modified time of the files stored in it."),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    add_target(parser_dir, command)

    # birth
    # target: year of birth
    command = "birth"
    parser_birth = subparsers.add_parser(
        command,
        help="search for active idols based on years of birth",
        description=
        ("description:\n"
         "  Search for active idols based on years of birth.\n\n"
         "examples:\n"
         "  search for 1990-born idols who are active in the recent year:\n"
         "    %(prog)s 1990\n"
         "  search for 1990-born idols who have uncensored and solo publications within 3 years:\n"
         "    %(prog)s -u -s -a 3 1990\n"),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser_birth.add_argument(
        "-a",
        dest="active",
        action="store",
        default="365D",
        type=date_within,
        help="active in this timespan (default %(default)s)")
    parser_birth.add_argument(
        "-u",
        dest="uncensored",
        action="store_true",
        help="uncensored only (default %(default)s)",
    )
    parser_birth.add_argument(
        "-s",
        dest="solo",
        action="store_true",
        help="solo only (default %(default)s)",
    )
    parser_birth.add_argument(
        dest="target",
        action="store",
        type=year_range,
        help=
        "year of birth, can be a single year (e.g. 1989) or a range (e.g. 1988-1991)",
    )

    args = parser.parse_args()

    # test target type
    # add args.type to Namespace
    if args.command in valid_types:
        target = Path(args.target)
        try:
            target = target.resolve(strict=True)
            args.type = "dir" if target.is_dir() else "file"
        except FileNotFoundError as e:
            if target.name != args.target:
                parser.error(e)
            target = target.stem
            args.type = "keyword"
        except (OSError, RuntimeError) as e:
            parser.error(e)
        if args.type not in valid_types[args.command]:
            parser.error('expect target to be "{}", not "{}".'.format(
                ", ".join(valid_types[args.command]), args.type))
        args.target = target

    return args


def date_within(date: str):

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


def year_range(years: str):

    m = re.fullmatch(r"\s*(\d{4})(?:-(\d{4}))?\s*", years)
    if m:
        return tuple(range(int(m[1]), int(m[2] or m[1]) + 1))
    raise argparse.ArgumentError()
