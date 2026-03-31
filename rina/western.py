import logging
import os
import re
import struct
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

import requests
from pymediainfo import MediaInfo

from . import network, utils
from .files import get_scanner
from .scraper import DateSearcher
from .utils import Status, re_search, strftime, strptime
from .video import _NAMEMAX, EXTS

_DUR_TOLERANCE = 30  # seconds
TPDB_API_LOC = "api.theporndb.net"
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Scene:
    site: str | None = None
    date: float | None = None
    performers: list[str] = field(default_factory=list)
    title: str | None = None
    file_dur: float | None = None
    api_dur: float | None = None
    resolution: str | None = None
    source: str | None = None


class WesternFile(utils.AVInfo):

    SAN_RE = r'[<>:"/\\|?*,!#\s.]+'
    keywidth = 10
    newpath: Path = None
    newdate: tuple = None

    def __init__(
        self,
        source,
        result: Scene | None,
        error: Exception | None = None,
    ):
        if not isinstance(source, Path):
            source = Path(source)
        self.source = source
        self.result = {"Target": source}

        if error:
            self.status = Status.ERROR
            self.result["Error"] = str(error)
            return

        if not result:
            self.status = Status.FAILURE
            self.result["Result"] = "Information not found."
            return

        self.status = Status.SUCCESS
        self.result.update(
            {
                "Site": result.site,
                "Date": strftime(result.date),
                "Performers": ", ".join(result.performers),
                "Title": result.title,
                "Resolution": result.resolution,
                "Source": result.source,
            }
        )

        file_dur = result.file_dur
        api_dur = result.api_dur
        if file_dur is not None and api_dur is not None:
            dur_diff = abs(api_dur - file_dur)
            self.result["Duration"] = (
                f"API: {_fmt_dur(api_dur)}  File: {_fmt_dur(file_dur)}  Diff: {dur_diff:.2f}s"
            )
            if dur_diff > _DUR_TOLERANCE:
                self.status = Status.WARNING
                self.result["Result"] = "Duration mismatch."
                return

        if result.title:
            newname = self._build_filename(result)
            if newname and newname != source.name:
                self.newpath = source.with_name(newname)
                self.result.update(OldName=source.name, NewName=self.newpath.name)
                self.status = Status.UPDATED

        if result.date:
            stat = source.stat()
            if abs(result.date - stat.st_mtime) > 1:
                self.newdate = (stat.st_atime, result.date)
                self.status = Status.UPDATED

    def _build_filename(self, result: Scene) -> str | None:
        """Construct a new filename: Site.Date.Performers.Title.Resolution.ext"""
        performers = (_sanitize(s, self.SAN_RE, ".") for s in result.performers)
        parts = (
            _sanitize(result.site, r"[^a-zA-Z0-9]+", ""),
            strftime(result.date, "%y.%m.%d"),
            ".and.".join(filter(None, performers)),
            _cap(_sanitize(result.title, self.SAN_RE, ".", _cap_non_small)),
            result.resolution,
        )
        stem = ".".join(filter(None, parts))

        namemax = _NAMEMAX - len(self.source.suffix) - 1
        if namemax <= 0:
            return
        if len(stem.encode()) > namemax:
            stem = stem.encode()[:namemax].decode(errors="ignore")
            cut = stem.rfind(".")
            if cut > 0:
                stem = stem[:cut]

        if re_search(r"\w", stem):
            return stem + self.source.suffix.lower()

    @utils.dryrun_method
    def apply(self):
        source = self.source
        if self.newpath:
            os.rename(source, self.newpath)
            source = self.newpath
        if self.newdate:
            os.utime(source, self.newdate)


_SMALL = {
    "a", "an", "the", "and", "as", "but", "for", "if", "nor", "or", "so",
    "yet", "at", "by", "in", "of", "off", "on", "per", "to", "up", "via"
} # fmt: skip


def _cap_non_small(text: str) -> str:
    """Capitalize the first letter of the text unless it's a small word."""
    lo = text.lower()
    return lo if lo in _SMALL else (text[:1].upper() + text[1:])


def _cap(text: str) -> str:
    """Capitalize the first letter of the text."""
    return text[:1].upper() + text[1:]


def _sanitize(text: str | None, split_re: str, sep: str, transform=_cap) -> str:
    """Split on regex, transform each piece, join with sep."""
    if not text:
        return ""
    return sep.join(transform(s) for s in re.split(split_re, text) if s)


def _fmt_dur(secs: int | float) -> str:
    m, s = divmod(int(secs), 60)
    return f"{m}m{s:02d}s"


def _oshash(path):
    """Compute OpenSubtitles hash (first+last 64KB + filesize)."""
    fsize = os.path.getsize(path)
    chunk = 64 * 1024
    with open(path, "rb") as f:
        head = f.read(chunk)
        f.seek(max(0, fsize - chunk))
        tail = f.read(chunk)
    n_head = len(head) // 8
    n_tail = len(tail) // 8
    h = fsize
    h += sum(struct.unpack(f"<{n_head}q", head[: n_head * 8]))
    h += sum(struct.unpack(f"<{n_tail}q", tail[: n_tail * 8]))
    return "%016x" % (h & 0xFFFFFFFFFFFFFFFF)


def _get_media_info(path):
    """Return (duration_secs, resolution_str) via pymediainfo."""
    try:
        info = MediaInfo.parse(path)
    except Exception:
        return None, None
    duration = height = None
    for track in info.tracks:
        if track.track_type == "General" and duration is None and track.duration:
            duration = track.duration / 1000
        elif track.track_type == "Video" and height is None:
            height = track.height
            if track.duration and duration is None:
                duration = track.duration / 1000
    res = None
    if height is not None:
        res = f"{height}p"
        for threshold, label in (
            (4320, "8k"),
            (3240, "6k"),
            (2000, "4k"),
            (1000, "1080p"),
            (680, "720p"),
            (440, "480p"),
            (300, "360p"),
        ):
            if height >= threshold:
                res = label
                break
    return duration, res


_PLATFORM_MAP = {
    "onlyfans": "OnlyFans",
    "manyvids": "ManyVids",
    "fansly": "Fansly",
    "pornhub": "Pornhub",
    "xvideos": "XVideos",
}
_PLATFORM_RE = rf"\b({'|'.join(_PLATFORM_MAP)})\b"


def _clean_site(scene: dict) -> str | None:
    """Normalize site name from TPDB data."""
    try:
        site = scene["site"]["name"]
    except KeyError:
        return
    m = re_search(_PLATFORM_RE, site, re.I)
    if m:
        return _PLATFORM_MAP[m[1].lower()]
    m = re_search(r"^\s*FansDB\s*:(?P<n1>.*?)(?:\((?P<n2>.+?)\))?\s*$", site, re.I)
    if m:
        site = m["n2"] or m["n1"]
    if re_search(r"\w", site):
        return site


def _clean_performers(scene: dict) -> list[str]:
    """Extract female performer names from scene data."""
    all_perfs = []
    female = []
    for p in scene.get("performers", ()):
        parent = p.get("parent") or {}
        name = parent.get("name") or p.get("name")
        if not name or not re_search(r"\w", name):
            continue
        all_perfs.append(name)
        extras = parent.get("extras") or p.get("extra")
        if extras and re_search(r"\bmale\b", extras.get("gender") or "", re.I):
            continue
        female.append(name)
    return female or all_perfs


def _set_api_key():
    """Ensure TPDB API key is set in network settings, prompt if not found. Must
    be called before TPDB API request."""
    api_key = utils.get_config().tpdb_api

    if not api_key:
        sys.stderr.write(
            "ThePornDB API key not found. Get one at https://www.theporndb.net/\n"
        )
        api_key = input("Enter API key: ").strip()
        if not api_key:
            sys.exit("API key is required.")
        utils.update_config(tpdb_api=api_key)

    network.set_settings(
        TPDB_API_LOC,
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
    )


def _scrape(path) -> Scene | None:
    """Hash file, query TPDB, validate duration, return TPDBScene or None."""
    try:
        r = network.get(f"https://{TPDB_API_LOC}/scenes?hash={_oshash(path)}")
        r.raise_for_status()
        scene = r.json().get("data")
    except requests.HTTPError as e:
        if e.response.status_code == 401:
            raise RuntimeError("Unauthorized. Check your API key.") from e
        logger.debug(e)
        return
    except (requests.RequestException, ValueError) as e:
        logger.warning(e)
        return

    if not scene:
        return
    scene = scene[0]
    title = scene.get("title", "").strip()
    if not title:
        return

    file_dur, resolution = _get_media_info(path)
    try:
        date = strptime(scene["date"], "%Y-%m-%d")
    except (KeyError, ValueError):
        date = None

    return Scene(
        site=_clean_site(scene),
        date=date,
        performers=_clean_performers(scene),
        title=title,
        file_dur=file_dur,
        api_dur=scene.get("duration"),
        resolution=resolution,
        source="TPDB",
    )


def from_path(path):
    """Analyze a file, returns a WesternFile object."""
    path = Path(path)
    try:
        result = _scrape(path)
        if not result:
            result = DateSearcher.search(path.stem, Scene)
        return WesternFile(path, result)
    except Exception as e:
        return WesternFile(path, None, e)


def from_args(args):
    """
    Scan a directory or file based on the provided arguments.
    :type args: argparse.Namespace
    """
    _set_api_key()

    if args.type == "file":
        yield from_path(args.source)
        return

    scanner = get_scanner(args, exts=EXTS)
    with ThreadPoolExecutor() as ex:
        for ft in as_completed(
            ex.submit(from_path, e.path) for e in scanner.scandir(args.source)
        ):
            yield ft.result()
