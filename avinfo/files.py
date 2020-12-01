import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from re import compile as re_compile
from re import search as re_search
from re import sub as re_sub

from avinfo import common
from avinfo.common import epoch_to_str, printer
from avinfo.videoscraper import scrapers


class AVString:

    _re_clean1 = re_compile(r"^(?:\[f?hd\]|[a-z0-9-]+\.[a-z]{2,}@)").sub
    _re_clean2 = re_compile(
        r"""
        \[[a-z0-9.-]+\.[a-z]{2,}\]|
        (?:^|[^a-z0-9])
        (?:168x|44x|3xplanet|sis001|sexinsex|thz|uncensored|nodrm|fhd|tokyo[\s_-]?hot|1000[\s_-]?girl)
        (?:[^a-z0-9]|$)""",
        flags=re.VERBOSE,
    ).sub

    def __init__(self, string: str):
        self.input = string
        self.string = self._re_clean2(" ", self._re_clean1("", string.lower()))
        self.scrape_result = self.exception = None
        # status: dateDiff filenameDiff success started
        self.status = 0

    def scrape(self):
        self.status |= 0b0001
        string = self.string

        try:
            self.scrape_result = next(filter(None, (s.run(string) for s in scrapers)))
        except StopIteration:
            pass
        except Exception as e:
            self.exception = e
        else:
            self.status |= 0b0010
            self._analyze_scrape()

        self._print_report()

    def _analyze_scrape(self):
        pass

    def _print_report(self):
        status = self.status
        if not status & 0b0001:
            raise RuntimeError("Generate report before scraping.")

        result = self.scrape_result
        logs = [("Target", self.input)]

        if result:
            if result.productId:
                logs.append(("ProductId", result.productId))
            if result.title:
                logs.append(("Title", result.title))
            if result.publishDate:
                logs.append(("Pub Date", epoch_to_str(result.publishDate)))
            if status & 0b1000:
                logs.append(("From Date", epoch_to_str(self.mtime)))
            if status & 0b0100:
                logs.append(("New Name", self.newfilename))
                logs.append(("From Name", self.path.name))
            logs.append(("Source", f"{result.titleSource or '---'} / {result.dateSource or '---'}"))
            sepLine = common.sepSuccess
            color = None
        else:
            if self.exception:
                logs.append(("Error", self.exception))
            sepLine = common.sepFailed
            color = "red"

        self.log = "".join(f'{k + ":":>10} {v}\n' for k, v in logs)
        printer(sepLine, self.log, color=color, end="")


class AVFile(AVString):

    video_filter = re_compile(
        r"\.(?:3gp|asf|avi|bdmv|flv|iso|m(?:2?ts|4p|[24kop]v|p2|p4|pe?g|xf)|rm|rmvb|ts|vob|webm|wmv)",
        flags=re.IGNORECASE,
    ).fullmatch

    def __init__(self, path: Path, stat: os.stat_result, namemax: int):
        super().__init__(path.stem)
        self.path = self.input = path
        self.atime = stat.st_atime
        self.mtime = stat.st_mtime
        self.namemax = namemax

    def scrape(self):
        if self.video_filter(self.path.suffix):
            super().scrape()
            if self.status & 0b1100:
                return self

    def _analyze_scrape(self):
        result = self.scrape_result

        productId = result.productId
        title = result.title
        if productId and title:
            newfilename = self._get_filename(productId, title)
            if newfilename != self.path.name:
                self.newfilename = newfilename
                self.status |= 0b0100

        publishDate = result.publishDate
        if publishDate and publishDate != self.mtime:
            self.status |= 0b1000

    def _get_filename(self, productId: str, title: str):

        suffix = self.path.suffix.lower()
        namemax = self.namemax - len(productId.encode("utf-8")) - len(suffix.encode("utf-8")) - 1

        title = re_sub(r'[\s<>:"/\\|?* 　]+', " ", title)
        title = self._strip_title(title)

        strategy = self._trim_title
        while len(title.encode("utf-8")) >= namemax:
            try:
                title = strategy(title)
            except TypeError:
                strategy = lambda s: s[:-1]
                title = strategy(title)
            title = self._strip_title(title)

        return f"{productId} {title}{suffix}"

    def _print_report(self):
        if self.status != 0b0011:
            super()._print_report()

    @staticmethod
    def _trim_title(title: str):
        return re_search(r"^.*\w[\s。！】」）…)\].]+", title)[0]

    @staticmethod
    def _strip_title(title: str):
        return re_sub(r"^[\s._]+|[\s【「（。、\[(.,_]+$", "", title)

    def apply(self) -> bool:
        try:
            if self.status & 0b0100:
                path = self.path.with_name(self.newfilename)
                os.rename(self.path, path)
                self.path = path

            if self.status & 0b1000:
                os.utime(self.path, (self.atime, self.scrape_result.publishDate))
        except OSError as e:
            self.exception = e
            return False
        return True


def handle_files(target: Path, quiet: bool):

    try:
        namemax = os.statvfs(target).f_namemax
    except OSError as e:
        namemax = 255
        printer(f"Error: Unable to detect max filename, using default (255). {e}", color="red")

    if target.is_dir():
        with ThreadPoolExecutor(max_workers=None) as ex:
            files = tuple(
                ex.submit(AVFile(p, s, namemax).scrape) for p, s, _ in common.walk_dir(target, filesOnly=True)
            )
        files = tuple(filter(None, (ft.result() for ft in files)))
    else:
        files = AVFile(target, target.stat(), namemax).scrape()
        if files:
            files = (files,)

    print(common.sepBold)
    if not files:
        print("File scan finished, no file can be modified.")
        return

    total = len(files)
    msg = f"""{total} files can be modified.
Please choose an option:
1) Apply changes.
2) Reload changes.
3) Quit without applying.
"""

    print(f"File scan finished.")
    while not quiet:

        choice = input(msg)
        if choice == "1":
            break
        elif choice == "3":
            sys.exit()

        print(common.sepBold)
        if choice == "2":
            common.log_printer(files)
        else:
            print("Invalid option.")
        print(common.sepBold)

    print("Applying changes...")
    errors = []
    sepLine = f"{common.sepSlim}\n"
    printProgressBar = common.printProgressBar
    printProgressBar(0, total)

    with open(common.logFile, "a", encoding="utf-8") as f:
        for i, avFile in enumerate(files, 1):
            if avFile.apply():
                f.write(f"[{epoch_to_str(None)}] File Update\n")
                f.write(avFile.log)
                f.write(sepLine)
            else:
                errors.extend(f"{i:>10} {j}" for i, j in (("Target:", avFile.target), ("Type:", avFile.exception)))
            printProgressBar(i, total)

    if errors:
        printer(f"{'Errors:':>10}\n", "\n".join(errors), color="red")


def handle_dirs(target: Path):

    if not target.is_dir():
        return

    def _change_mtime(path: Path, stat: os.stat_result):
        try:
            record = records[path]
        except KeyError:
            return False

        mtime = stat.st_mtime
        if record != mtime:
            try:
                os.utime(path, (stat.st_atime, record))
            except OSError as e:
                printer(f"Error: {path.name}  ({e})", color="red")
            else:
                print(f"{epoch_to_str(mtime, '%F')}  ==>  {epoch_to_str(record, '%F')}  {path.name}")
                return True

        return False

    print(common.sepBold)
    print("Scanning directory timestamps...")

    records = {}
    total = 1
    success = 0

    for path, stat, is_dir in common.walk_dir(target, filesOnly=False):
        if is_dir:
            total += 1
            success += _change_mtime(path, stat)
        else:
            mtime = stat.st_mtime
            for parent in path.parents:
                if records.get(parent, -1) < mtime:
                    records[parent] = mtime
                if parent == target:
                    break

    success += _change_mtime(target, target.stat())

    print(f"Finished. {total} dirs scanned, {success} modified.")
