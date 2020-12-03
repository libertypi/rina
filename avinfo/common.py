from datetime import datetime, timezone
from functools import lru_cache
from os import scandir
from pathlib import Path
from re import compile as re_compile
from time import sleep

from bs4 import UnicodeDammit
from lxml.etree import XPath
from lxml.html import HtmlElement, fromstring
from requests import RequestException, Session

logFile = "logfile.log"
sepWidth = 50
sepBold = "=" * sepWidth
sepSlim = "-" * sepWidth
sepSuccess = "SUCCESS".center(sepWidth, "-") + "\n"
sepFailed = "FAILED".center(sepWidth, "-") + "\n"
sepChanged = "CHANGED".center(sepWidth, "-") + "\n"
session = Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:80.0) Gecko/20100101 Firefox/80.0"})


_colors = {"red": "\033[31m", "yellow": "\033[33m"}


def color_printer(*args, color: str, **kwargs):
    print(_colors[color], end="")
    print(*args, **kwargs)
    print("\033[0m", end="")


def printProgressBar(iteration, total, prefix="Progress", suffix="Complete", length=sepWidth, fill="█", printEnd="\r"):
    percent = f"{100 * (iteration / float(total)):.1f}"
    filledLength = int(length * iteration // total)
    bar = f'{fill * filledLength}{"-" * (length - filledLength)}'
    print(f"\r{prefix} |{bar}| {percent}% {suffix}", end=printEnd)
    if iteration == total:
        print()


def _path_filter(name: str):
    return name.startswith(("#", "@", "."))


def walk_dir(topDir: Path, filesOnly: bool = False):
    """Recursively yield 3-tuples of (path, stat, is_dir) in a bottom-top order."""

    with scandir(topDir) as it:
        for entry in it:
            if _path_filter(entry.name):
                continue
            path = Path(entry.path)
            try:
                is_dir = entry.is_dir()
                if is_dir:
                    yield from walk_dir(path, filesOnly)
                    if filesOnly:
                        continue
                yield path, entry.stat(), is_dir
            except OSError as e:
                color_printer(f"Error occurred scanning {entry.path}: {e}", color="red")


def list_dir(topDir: Path):
    """List dir paths under top."""

    with scandir(topDir) as it:
        for entry in it:
            try:
                if entry.is_dir() and not _path_filter(entry.name):
                    yield Path(entry.path)
            except OSError as e:
                color_printer(f"Error occurred scanning {entry.path}: {e}", color="red")
    if not _path_filter(topDir.name):
        yield Path(topDir)


def get_response_tree(url, *, decoder: str = None, **kwargs):
    """Input args to requests, output (response, tree)

    :params: decoder: bs4, lxml, or any encoding code.
    :params: bs4_hint: code for bs4 to try
    """
    for retry in range(3):
        try:
            response = session.get(url, **kwargs, timeout=(7, 28))
        except RequestException:
            if retry == 2:
                raise
            sleep(1)
        else:
            break
    else:
        raise RequestException(url)

    if response.ok:
        if not decoder:
            content = UnicodeDammit(
                response.content,
                override_encodings=("utf-8", "euc-jp"),
                is_html=True,
            ).unicode_markup
        elif decoder == "lxml":
            content = response.content
        else:
            response.encoding = decoder
            content = response.text
        tree: HtmlElement = fromstring(content)
    else:
        tree = None
    return response, tree


def str_to_epoch(string: str, dFormat: str = "%Y %m %d", regex=re_compile(r"[^0-9]+")) -> float:
    if regex:
        string = regex.sub(" ", string).strip()
    return datetime.strptime(string, dFormat).replace(tzinfo=timezone.utc).timestamp()


def epoch_to_str(epoch: float, dFormat: str = "%F %T"):
    try:
        return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime(dFormat)
    except TypeError:
        pass


def now(fmt: str = "%F %T"):
    return datetime.now().strftime(fmt)


@lru_cache(maxsize=128)
def xp_compile(xpath: str):
    return XPath(xpath)
