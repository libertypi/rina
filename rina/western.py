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

from . import files, network, utils
from .scraper import DateSearcher
from .utils import AVInfo, Status, re_search, strftime, strptime
from .video import _NAMEMAX, EXTS

DUR_TOLERANCE = 120  # seconds
TPDB_API_LOC = "api.theporndb.net"
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Scene:
    site: str | None = None
    date: float | None = None
    performers: list[str] = field(default_factory=list)
    title: str | None = None
    resolution: str | None = None
    diff: float | None = None
    source: str | None = None


class WesternFile(AVInfo):

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
            Site=result.site,
            Date=strftime(result.date),
            Performers=", ".join(result.performers),
            Title=result.title,
            Resolution=result.resolution,
            Difference=None if result.diff is None else f"{result.diff:.2f}s",
            Source=result.source,
        )
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
        performers = (sanitize(s, self.SAN_RE, ".") for s in result.performers)
        parts = (
            sanitize(result.site, r"[^a-zA-Z0-9]+", ""),
            strftime(result.date, "%y.%m.%d"),
            ".and.".join(filter(None, performers)),
            sanitize(result.title, self.SAN_RE, ".", title_case=True),
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


def sanitize(text: str, splitter: str, joiner: str, title_case: bool = False) -> str:
    """
    Sanitize a string by splitting with a regex, filtering empty parts, and
    joining with a specified character. Capitalize the first letter of each
    word. Follow title case rules if title_case is True.
    """
    if not text:
        return ""
    parts = filter(None, re.split(splitter, text))
    if title_case:
        return joiner.join(_titleize(parts))
    return joiner.join(s[:1].upper() + s[1:] for s in parts)


def _titleize(parts):
    first = True
    for s in parts:
        lo = s.lower()
        if lo in _SMALL:
            if not first:
                yield lo
                continue
            s = lo
        yield s[:1].upper() + s[1:]
        first = False


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


def set_api_key():
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
        site = scene["site"]["name"].strip()
    except (KeyError, AttributeError):
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
    """Extract non-male performer names from scene data."""
    all_perfs = []
    female = []
    for p in scene.get("performers", ()):
        try:
            parent = p.get("parent") or {}
            name = parent.get("name") or p.get("name")
            if not name or not re_search(r"\w", name):
                continue
            all_perfs.append(name)
            extras = parent.get("extras") or p.get("extra")
            if extras and re_search(r"\bmale\b", extras.get("gender") or "", re.I):
                continue
            female.append(name)
        except Exception as e:
            logger.warning("Error processing performer data: %s", e)
    return female or all_perfs


def _scrape(path) -> Scene | None:
    """Hash file, query TPDB, validate duration, return TPDBScene or None."""
    try:
        r = network.get(f"https://{TPDB_API_LOC}/scenes?hash={_oshash(path)}")
        r.raise_for_status()
        data = r.json().get("data")
    except requests.HTTPError as e:
        if e.response.status_code == 401:
            logger.error("Unauthorized: Invalid TPDB API key.")
        else:
            logger.debug(e)
        return
    except Exception as e:
        logger.warning(e)
        return
    if not data or not isinstance(data, list):
        return

    # pick the best match based on duration diff
    file_dur, resolution = _get_media_info(path)
    best = None, None, None  # diff, scene, title
    for scene in data:
        try:
            title = scene["title"].strip()
            if not title:
                continue
            api_dur = scene.get("duration")
            if file_dur is not None and api_dur is not None:
                diff = abs(api_dur - file_dur)
                if diff > DUR_TOLERANCE:
                    continue
                if best[0] is None or best[0] > diff:
                    best = diff, scene, title
            elif best[1] is None:
                best = None, scene, title
        except Exception as e:
            logger.warning("Error processing scene data: %s", e)
    diff, scene, title = best
    if scene is None:
        return

    try:
        date = strptime(scene["date"], "%Y-%m-%d")
    except (KeyError, ValueError):
        date = None

    return Scene(
        site=_clean_site(scene),
        date=date,
        performers=_clean_performers(scene),
        title=title,
        resolution=resolution,
        diff=diff,
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
    set_api_key()

    if args.type == "file":
        yield from_path(args.source)
        return

    scanner = files.get_scanner(args, exts=EXTS)
    with ThreadPoolExecutor() as ex:
        for ft in as_completed(
            ex.submit(from_path, e.path) for e in scanner.scandir(args.source)
        ):
            yield ft.result()
