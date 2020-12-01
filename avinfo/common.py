from datetime import datetime, timezone
from functools import lru_cache
from os import scandir
from pathlib import Path
from re import compile as re_compile
from time import sleep

from requests import Session, RequestException
from bs4 import UnicodeDammit
from lxml.etree import XPath
from lxml.html import HtmlElement, fromstring

logFile = Path("logfile.log")
sepWidth = 50
sepBold = "=" * sepWidth
sepSlim = "-" * sepWidth
sepSuccess = "SUCCESS".center(sepWidth, "-") + "\n"
sepFailed = "FAILED".center(sepWidth, "-") + "\n"
sepChanged = "CHANGED".center(sepWidth, "-") + "\n"
session = Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:80.0) Gecko/20100101 Firefox/80.0"})


def printRed(arg, **kargs):
    print(f"\033[31m{arg}\033[0m", **kargs)


def printYellow(arg, **kargs):
    print(f"\033[33m{arg}\033[0m", **kargs)


def printProgressBar(iteration, total, prefix="Progress", suffix="Complete", length=sepWidth, fill="█", printEnd="\r"):
    percent = f"{100 * (iteration / float(total)):.1f}"
    filledLength = int(length * iteration // total)
    bar = f'{fill * filledLength}{"-" * (length - filledLength)}'
    print(f"\r{prefix} |{bar}| {percent}% {suffix}", end=printEnd)
    if iteration == total:
        print()


def printObjLogs(lst, printer=print):
    for i, obj in enumerate(lst, 1):
        printer(f'{"No":>10}: {i}\n{obj.log}{sepSlim}')


def _path_filter(name: str):
    return name.startswith(("#", "@", "."))


def walk_dir(topDir: Path, filesOnly=False):
    """Recursively yield tuples of dir entries in a bottom-top order."""

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
                printRed(f"Error occurred scanning {entry.path}: {e}")


def list_dir(topDir: Path):
    """List only dirs under top."""
    with scandir(topDir) as it:
        for entry in it:
            try:
                if entry.is_dir() and not _path_filter(entry.name):
                    yield Path(entry.path)
            except OSError as e:
                printRed(f"Error occurred scanning {entry.path}: {e}")
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


def epoch_to_str(epoch: float, dFormat: str = "%F %T") -> str:
    if epoch is None:
        return datetime.now().strftime(dFormat)
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime(dFormat)


@lru_cache(maxsize=128)
def xp_compile(xpath: str):
    return XPath(xpath)


def contains_cjk():
    mask = 0
    for i, j in (
        (4352, 4607),
        (11904, 42191),
        (43072, 43135),
        (44032, 55215),
        (63744, 64255),
        (65072, 65103),
        (65381, 65500),
        (131072, 196607),
    ):
        mask |= (1 << j + 1) - (1 << i)

    def _contains_cjk(string: str) -> bool:
        return any(1 << ord(c) & mask for c in string)

    return _contains_cjk


contains_cjk = contains_cjk()
