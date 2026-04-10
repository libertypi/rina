import logging
import os
import re
import struct
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

import requests
from pymediainfo import MediaInfo

from . import files, network, utils
from .scraper import DateSearcher
from .utils import AVInfo, Status, stderr_write, strftime, strptime
from .video import EXTS, NAMEMAX

DUR_TOLERANCE = 120  # seconds

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Scene:
    """Scraper result for a single scene."""

    site: str | None = None
    date: float | None = None
    performers: list[str] = field(default_factory=list)
    title: str | None = None
    resolution: str | None = None
    diff: float | None = None
    source: str | None = None


class WesternFile(AVInfo):
    """A western video file paired with its scraped Scene metadata."""

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

        namemax = NAMEMAX - len(self.source.suffix) - 1
        if namemax <= 0:
            return
        if len(stem.encode()) > namemax:
            stem = stem.encode()[:namemax].decode(errors="ignore")
            cut = stem.rfind(".")
            if cut > 0:
                stem = stem[:cut]

        if re.search(r"\w", stem):
            return stem + self.source.suffix.lower()

    @utils.dryrun_method
    def apply(self):
        source = self.source
        if self.newpath:
            os.rename(source, self.newpath)
            source = self.newpath
        if self.newdate:
            os.utime(source, self.newdate)


class Scraper(ABC):
    """Base scraper: fetch scenes by oshash, pick best match by duration."""

    def __init__(self, netloc: str, headers: dict):
        network.set_settings(netloc, headers=headers)
        self.name = self.__class__.__name__.removesuffix("Scraper")

    def scrape(
        self, hash: str, file_dur: float | None, resolution: str | None
    ) -> Scene | None:
        """Fetch scenes by hash, return the closest duration match."""
        try:
            data = self._fetch(hash)
        except requests.HTTPError as e:
            if e.response.status_code == 401:
                logger.error("Unauthorized: Invalid %s API key.", self.name)
            else:
                logger.debug(e)
            return
        except Exception as e:
            logger.warning(e)
            return
        if not data or not isinstance(data, list):
            return

        best = None, None, None  # diff, scene, title
        for scene in data:
            try:
                title = scene["title"].strip()
                if not title:
                    continue
                if file_dur is None:
                    best = None, scene, title
                    break
                api_dur = scene.get("duration")
                if api_dur is not None:
                    diff = abs(api_dur - file_dur)
                    if diff > DUR_TOLERANCE:
                        continue
                    if best[0] is None or best[0] > diff:
                        best = diff, scene, title
                elif best[1] is None:
                    best = None, scene, title
            except Exception as e:
                logger.warning("Error processing %s scene data: %s", self.name, e)
        diff, scene, title = best
        if scene is None:
            return

        try:
            date = strptime(scene["date"], "%Y-%m-%d")
        except (KeyError, ValueError):
            date = None

        return Scene(
            site=self._parse_site(scene),
            date=date,
            performers=self._parse_performers(scene),
            title=title,
            resolution=resolution,
            diff=diff,
            source=self.name,
        )

    @abstractmethod
    def _fetch(self, hash) -> list[dict]: ...

    @abstractmethod
    def _parse_site(self, scene) -> str | None: ...

    @abstractmethod
    def _parse_performers(self, scene) -> list[str]: ...


class TPDBScraper(Scraper):
    """ThePornDB (theporndb.net) REST scraper."""

    _API_LOC = "api.theporndb.net"
    _PLATFORMS = ("OnlyFans", "ManyVids", "Fansly", "Pornhub", "XVideos")
    _PLATFORM_RE = r"\b(?:{})\b".format("|".join(rf"({p})" for p in _PLATFORMS))

    def __init__(self, api_key):
        super().__init__(
            self._API_LOC,
            {"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        )

    def _fetch(self, hash):
        r = network.request(f"https://{self._API_LOC}/scenes?hash={hash}")
        r.raise_for_status()
        return r.json()["data"]

    def _parse_site(self, scene):
        try:
            site = scene["site"]["name"].strip()
        except (KeyError, AttributeError):
            return
        m = re.search(self._PLATFORM_RE, site, re.I)
        if m:
            return self._PLATFORMS[m.lastindex - 1]
        m = re.search(r"^\s*FansDB\s*:(?P<n1>.*?)(?:\((?P<n2>.+?)\))?\s*$", site, re.I)
        if m:
            site = m["n2"] or m["n1"]
        if re.search(r"\w", site):
            return site

    def _parse_performers(self, scene):
        performers = []
        for p in scene.get("performers", ()):
            try:
                parent = p.get("parent") or {}
                name = parent.get("name") or p.get("name")
                if not name or not re.search(r"\w", name):
                    continue
                extras = parent.get("extras") or p.get("extra")
                if extras and re.search(r"\bmale\b", extras.get("gender") or "", re.I):
                    continue
                performers.append(name)
            except Exception as e:
                logger.warning("Error processing performer data: %s", e)
        return performers


class StashDBScraper(Scraper):
    """StashDB (stashdb.org) GraphQL scraper."""

    _API_LOC = "stashdb.org"
    _GQL = f"https://{_API_LOC}/graphql"
    _QUERY = """
    query($hash: String!) {
        findSceneByFingerprint(fingerprint: {hash: $hash, algorithm: OSHASH}) {
            title
            date
            duration
            studio { name }
            performers { as performer { name gender } }
        }
    }"""

    def __init__(self, api_key):
        super().__init__(
            self._API_LOC,
            {"ApiKey": api_key, "Content-Type": "application/json"},
        )

    def _fetch(self, hash):
        r = network.request(
            self._GQL,
            method="POST",
            json={"query": self._QUERY, "variables": {"hash": hash}},
        )
        r.raise_for_status()
        return r.json()["data"]["findSceneByFingerprint"]

    def _parse_site(self, scene):
        try:
            return scene["studio"]["name"].strip()
        except (KeyError, TypeError, AttributeError):
            return

    def _parse_performers(self, scene):
        performers = []
        for p in scene.get("performers", ()):
            try:
                perf = p.get("performer") or {}
                name = perf.get("name")
                if not name or not re.search(r"\w", name):
                    continue
                if re.search(r"\bmale\b", perf.get("gender") or "", re.I):
                    continue
                performers.append(name)
            except Exception as e:
                logger.warning("Error processing performer data: %s", e)
        return performers


def sanitize(text: str, splitter: str, joiner: str, title_case: bool = False) -> str:
    """
    Sanitize a string by splitting with a regex, filtering empty parts, and
    joining with a specified character. Capitalize the first letter of each
    word. Follow title case rules if title_case is True.
    """
    if not text:
        return ""
    if title_case and text.isupper():
        text = text.lower()
    parts = filter(None, re.split(splitter, text))
    if title_case:
        return joiner.join(_titleize(parts))
    return joiner.join(s[:1].upper() + s[1:] for s in parts)


_SMALL = {
    "a", "an", "the", "and", "as", "but", "for", "if", "nor", "or", "so",
    "yet", "at", "by", "in", "of", "off", "on", "per", "to", "up", "via"
} # fmt: skip


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
            (200, "240p"),
        ):
            if height >= threshold:
                res = label
                break
    return duration, res


def get_scrapers() -> list[Scraper]:
    """Build scrapers for whichever API keys are configured."""
    scrapers = []
    config = utils.get_config()
    if config.tpdb_api:
        scrapers.append(TPDBScraper(config.tpdb_api))
    if config.stashdb_api:
        scrapers.append(StashDBScraper(config.stashdb_api))
    return scrapers


def from_path(path, scrapers: list[Scraper]):
    """Analyze a file, returns a WesternFile object."""
    path = Path(path)
    try:
        hash = _oshash(path)
        file_dur, resolution = _get_media_info(path)
        result = None
        for scraper in scrapers:
            result = scraper.scrape(hash, file_dur, resolution)
            if result:
                break
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
    scrapers = get_scrapers()
    if not scrapers:
        stderr_write(
            "No scraper API keys configured. Set one with:\n"
            "    rina set tpdb_api YOUR_KEY\n"
            "    rina set stashdb_api YOUR_KEY\n"
        )
        return

    if args.type == "file":
        yield from_path(args.source, scrapers)
        return

    scanner = files.get_scanner(args, exts=EXTS)
    with ThreadPoolExecutor() as ex:
        for ft in as_completed(
            ex.submit(from_path, e.path, scrapers) for e in scanner.scandir(args.source)
        ):
            yield ft.result()
