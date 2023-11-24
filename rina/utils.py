import logging
import re
import sys
import time
from abc import ABC
from datetime import datetime, timezone
from enum import Enum, StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Optional

SEP_WIDTH = 50
SEP_BOLD = "=" * SEP_WIDTH
SEP_SLIM = "-" * SEP_WIDTH

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

logging.basicConfig(format="%(levelname)s: %(message)s")


class Color(StrEnum):
    RED = "\033[31m"
    YELLOW = "\033[33m"
    MAGENTA = "\033[35m"
    BRIGHT_RED = "\033[91m"


class Status(Enum):
    SUCCESS = None
    UPDATED = Color.YELLOW
    FAILURE = Color.RED
    WARNING = Color.MAGENTA
    ERROR = Color.BRIGHT_RED


if sys.stdout.isatty():

    def color_writer(string: str, color: Color = None, file=sys.stdout):
        file.write(string if color is None else f"{color}{string}\033[0m")

else:

    def color_writer(string: str, color: Color = None, file=sys.stdout):
        file.write(string)


class AVInfo(ABC):
    """
    Abstract base class for handling AV information, providing a structure for
    result storage, presentation, and file operations.
    """

    # Structured result of media processing, for report generation
    # result: dict[str, Union[str, tuple]]
    result: dict = None
    # Tracks the current status of the media (e.g., SUCCESS, FAILURE)
    status: Status = None
    # Used for formatting output
    keywidth: int = None
    # Cached text for report generation
    _headers: dict = {}
    _report: str = None

    def print(self):
        """
        Method to format and print media information.
        """
        status = self.status
        if self._report is None:
            # Create a header for the current status
            try:
                items = [self._headers[status.name]]
            except KeyError:
                items = ["{0:-^{1}}\n".format(f" {status.name} ", SEP_WIDTH)]
                self._headers[status.name] = items[0]
            # Determine the key width
            kw = self.keywidth or max(map(len, self.result))
            # Format each key-value pair in the result
            for k, v in self.result.items():
                if not v:
                    continue
                if isinstance(v, tuple):
                    v = iter(v)
                    items.append(f"{k:>{kw}}: {next(v)}\n")
                    items.extend(f'{"":>{kw}}  {i}\n' for i in v)
                else:
                    items.append(f"{k:>{kw}}: {v}\n")
            # Combine into a single text
            self._report = "".join(items)
        color_writer(self._report, color=status.value)

    def apply(self):
        raise NotImplementedError


def get_choice_as_int(msg: str, total: int) -> int:
    while True:
        stderr_write(msg)
        try:
            choice = int(input())
        except ValueError:
            stderr_write("Please enter a valid number.\n")
            continue
        if 1 <= choice <= total:
            return choice
        stderr_write(f"Invalid option. Please enter a number from 1 to {total}.\n")


def strptime(string: str, fmt: str) -> float:
    """Parse a string acroding to a format, returns epoch in UTC."""
    return datetime.strptime(string, fmt).replace(tzinfo=timezone.utc).timestamp()


def strftime(epoch: float, fmt: str = "%F") -> Optional[str]:
    """Convert an epoch timestamp in UTC to a string."""
    if epoch is not None:
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


def two_digit_regex(lower: int, upper: int):
    """
    Generate a regex pattern to match all two-digit numbers from 'lower' to
    'upper'.

    Examples:
     - (20, 59) -> '[2-5][0-9]'
     - ( 0, 23) -> '[01][0-9]|2[0-3]'
     - (21, 55) -> '2[1-9]|[34][0-9]|5[0-5]
    """
    if not (0 <= lower <= upper <= 99):
        raise ValueError(f"Values out of range: lower={lower}, upper={upper}")

    def drange(x, y):
        d = y - x
        return f"[{x}-{y}]" if d > 1 else f"[{x}{y}]" if d else f"{x}"

    ltens, lones = divmod(lower, 10)
    utens, uones = divmod(upper, 10)
    if ltens == utens:
        return f"{ltens}{drange(lones, uones)}"
    parts = []
    # Lower part, if it does not start from 0
    if lones > 0:
        parts.append(f"{ltens}{drange(lones, 9)}")
        ltens += 1
    # Middle and upper part
    if ltens < utens and uones < 9:
        parts.append(f"{drange(ltens, utens - 1)}[0-9]|{utens}{drange(0, uones)}")
    else:
        parts.append(f"{drange(ltens, utens)}{drange(0, uones)}")
    return "|".join(parts)
