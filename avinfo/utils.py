import re
import sys
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Optional

SEP_WIDTH = 50
SEP_BOLD = "=" * SEP_WIDTH
SEP_SLIM = "-" * SEP_WIDTH
SEP_SUCCESS = " SUCCESS ".center(SEP_WIDTH, "-")
SEP_FAILED = " FAILED ".center(SEP_WIDTH, "-")
SEP_CHANGED = " CHANGED ".center(SEP_WIDTH, "-")


join_root = Path(__file__).parent.joinpath
stderr_write = sys.stderr.write
date_searcher = re.compile(
    r"""(?P<y>(?:[1１][9９]|[2２][0０])\d\d)\s*
    (?:(?P<han>年)|(?P<sep>[／/.－-]))\s*
    (?P<m>[1１][0-2０-２]|[0０]?[1-9１-９])\s*
    (?(han)月|(?P=sep))\s*
    (?P<d>[12１２][0-9０-９]|[3３][01０１]|[0０]?[1-9１-９])
    (?(han)\s*日|(?=$|\D))""",
    flags=re.VERBOSE,
).search


if sys.stdout.isatty():

    def color_printer(*args, sep=None, end=None, red: bool = True):
        """Print text to stdout in red or yellow color."""
        print("\033[31m" if red else "\033[33m", end="")
        print(*args, sep=sep, end=end)
        print("\033[0m", end="", flush=True)

else:

    def color_printer(*args, sep=None, end=None, red: bool = True):
        print(*args, sep=sep, end=end)


def get_choice_as_int(msg: str, max_opt: int) -> int:
    while True:
        stderr_write(msg)
        try:
            choice = int(input())
        except ValueError:
            pass
        else:
            if 1 <= choice <= max_opt:
                return choice
        stderr_write("Invalid option.\n")


def strptime(string: str, fmt: str) -> float:
    """Parse a string acroding to a format, returns epoch in UTC."""
    return datetime.strptime(string, fmt).replace(tzinfo=timezone.utc).timestamp()


def strftime(epoch: float, fmt: str = "%F") -> Optional[str]:
    """Convert an epoch timestamp in UTC to a string."""
    if isinstance(epoch, (float, int)):
        return time.strftime(fmt, time.gmtime(epoch))


def str_to_epoch(string: str) -> Optional[float]:
    """Search for YYYY-MM-DD like date in a string, returns UTC epoch timestamp."""
    try:
        m = date_searcher(string)
        return datetime(
            int(m["y"]),
            int(m["m"]),
            int(m["d"]),
            tzinfo=timezone.utc,
        ).timestamp()
    except (TypeError, ValueError):
        pass


@lru_cache
def cached_compile(pattern: str, flags: int = 0):
    return re.compile(pattern, flags)


def re_search(pattern: str, string: str, flags: int = 0):
    return cached_compile(pattern, flags).search(string)


def re_sub(pattern: str, repl, string: str, count: int = 0, flags: int = 0):
    return cached_compile(pattern, flags).sub(repl, string, count)


def re_subn(pattern: str, repl, string: str, count: int = 0, flags: int = 0):
    return cached_compile(pattern, flags).subn(repl, string, count)
