import calendar
import os
import re
import time

import requests
from bs4 import UnicodeDammit
from lxml import html

logFile = "logfile.log"
sepWidth = 50
sepBold = "=" * sepWidth
sepSlim = "-" * sepWidth
sepSuccess = f'{"SUCCESS".center(sepWidth, "-")}\n'
sepFailed = f'{"FAILED".center(sepWidth, "-")}\n'
sepChanged = f'{"CHANGED".center(sepWidth, "-")}\n'
session = requests.session()
session.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36"
    }
)


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


def walk_dir(topDir: str, filesOnly=False, nameFilter=re.compile(r"[#@.]")) -> tuple:
    """Recursively yield tuples of dir entries in a bottom-top order:
    (fullpath: str, stat: os.stat_result, isdir: bool)
    """
    with os.scandir(topDir) as it:
        for entry in it:
            if nameFilter.match(entry.name):
                continue
            try:
                isdir = entry.is_dir()
                if isdir:
                    yield from walk_dir(entry.path, filesOnly, nameFilter)
                    if filesOnly:
                        continue
                yield entry.path, entry.stat(), isdir
            except OSError as e:
                printRed(f"Error occurred scanning {entry.path}: {e}")


def list_dir(topDir: str, nameFilter=re.compile(r"[.#@]")) -> tuple:
    """List only dirs under top."""
    with os.scandir(topDir) as it:
        for entry in it:
            try:
                if entry.is_dir() and not nameFilter.match(entry.name):
                    yield entry.name, entry.path
            except OSError as e:
                printRed(f"Error occurred scanning {entry.path}: {e}")
    if not nameFilter.match(topDir):
        yield os.path.basename(topDir), topDir


def get_response_tree(url, decoder="bs4", bs4_hint=("utf-8", "euc-jp"), **kwargs) -> tuple:
    """Input args to requests, output (response, tree)
    :decoder: bs4, lxml, or any encoding code.
    :bs4_hint: code for bs4 to try
    """
    for retry in range(3):
        try:
            response = session.get(url, **kwargs, timeout=(7, 28))
            break
        except requests.ConnectionError as e:
            if retry == 2:
                raise e
            time.sleep(1)

    if response.ok:
        if decoder == "bs4":
            content = UnicodeDammit(response.content, override_encodings=bs4_hint, is_html=True).unicode_markup
        elif decoder == "lxml":
            content = response.content
        else:
            response.encoding = decoder
            content = response.text
        tree = html.fromstring(content)
    else:
        tree = None
    return response, tree


def str_to_epoch(string: str, dFormat="%Y %m %d", regex=re.compile(r"[^0-9]+")) -> float:
    if regex:
        string = regex.sub(" ", string).strip()
    return calendar.timegm(time.strptime(string, dFormat))


def epoch_to_str(epoch: float, dFormat="%F %T") -> str:
    return time.strftime(dFormat, time.gmtime(epoch)) if epoch else time.strftime(dFormat)
