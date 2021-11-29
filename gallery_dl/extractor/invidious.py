#!/usr/bin/env python
# -*- coding: utf-8 -*-
import itertools
import typing as T
from urllib import parse

from .common import Extractor, Message

BASE_DOMAIN = "localhost:3000"
BASE_PATTERN = r"(?:https?://)?{}".format(BASE_DOMAIN)


class InvidiousExtractor(Extractor):
    category = "invidious"


def get_api_url(
    path, page: T.Optional[str] = None, sort_by: T.Optional[str] = None
) -> str:
    url = f"http://{BASE_DOMAIN}/api/v1/{path}"
    new_query = {}
    if page:
        new_query["page"] = page
    if sort_by:
        new_query["sort_by"] = sort_by
    if page:
        url = parse.urlparse(url)._replace(query=parse.urlencode(new_query)).geturl()
    return url


class InvidiousChannelExtractor(InvidiousExtractor):
    pattern = BASE_PATTERN + r"/channel/.+"
    subcategory = "channel"
    page: T.Optional[str]

    def items(self):
        """extract items.

        example paths:
        - /channel/ucid
        - /channel/ucid/playlists
        """
        #  @note comments not send
        page = get_page_query(self.url)
        paths = parse.urlparse(self.url).path.split("/")
        channel_id = paths[2]
        is_playlists = next(itertools.islice(paths, 3, None), None)
        if not is_playlists:
            yield Message.Queue, get_api_url(
                path=f"channels/videos/{channel_id}", page=page
            ), {}
        # only send playlist page from first channel page
        if not page or page == "1" or is_playlists:
            yield Message.Queue, get_api_url(
                path=f"channels/playlists/{channel_id}", page=page
            ), {}


class InvidiousApiChannelsExtractor(InvidiousExtractor):
    pattern = BASE_PATTERN + r"/api/v1/channels/.+"
    subcategory = "api-channels"

    def items(self):
        """extract urls.

        example url paths:

        - /api/v1/channels/playlists/ucid
        - /api/v1/channels/ucid/playlists
        - /api/v1/channels/ucid/videos
        - /api/v1/channels/videos/ucid
        """
        resp_json = self.request(self.url).json()
        p_url = parse.urlparse(self.url)
        paths = p_url.path.split("/")
        paths4 = paths[4]
        paths5 = next(itertools.islice(paths, 5, None), "")
        sort_by = None
        page = None
        if p_url.query:
            page = parse.parse_qs(p_url.query).get("page", [None])[0]
            sort_by = parse.parse_qs(p_url.query).get("sort_by", [None])[0]
        channel_id = paths4 if paths4 not in ("playlists", "videos") else paths5
        video_ids = set()
        playlist_ids = set()
        if (paths4 == "playlists" and paths5) or (paths5 == "playlists" and paths4):
            for playlist in resp_json.get("playlists", []):
                if playlist_id := playlist.get("playlistId", None):
                    playlist_ids.add(playlist_id)
                for video in playlist.get("videos", []):
                    if video_id := video.get("videoId", None):
                        video_ids.add(video_id)
        elif (paths4 == "videos" and paths5) or (paths5 == "videos" and paths4):
            for video in resp_json:
                if video_id := video.get("videoId", None):
                    video_ids.add(video_id)
            if video_ids:
                next_page = int(page) + 1 if page is not None else 2
                yield Message.Queue, get_api_url(
                    f"channels/videos/{channel_id}",
                    page=str(next_page),
                    sort_by=sort_by,
                ), {}
            else:
                self.log.debug("no url,%s", self.url)
        else:
            raise ValueError("unknown format, %s", self.url)
        for key, ids, fmt in [
            (Message.Queue, playlist_ids, "http://{domain}/api/v1/playlists/{id_}"),
            (Message.Url, video_ids, "http://localhost:3000/watch?v={id_}"),
        ]:
            #  invidious
            for id_ in ids:
                yield key, fmt.format(id_=id_, domain=BASE_DOMAIN), {}


def get_api_playlists_url(playlist_id: str, page: T.Optional[str] = None) -> str:
    return get_api_url(path=f"playlists/{playlist_id}", page=page)


def get_page_query(url: str) -> T.Optional[str]:
    page = None
    if (p_url := parse.urlparse(url)) and p_url.query:
        page = parse.parse_qs(p_url.query).get("page", [None])[0]
    return page


class InvidiousPlaylistExtractor(InvidiousExtractor):
    pattern = BASE_PATTERN + r"/playlist\?list=([^&]+)"
    subcategory = "playlist"

    def __init__(self, match):
        super().__init__(match)
        self.playlist_id = match.group(1)

    def items(self):
        yield Message.Queue, get_api_playlists_url(
            self.playlist_id, get_page_query(self.url)
        ), {}


class InvidiousApiPlaylistsExtractor(InvidiousExtractor):
    pattern = BASE_PATTERN + r"/api/v1/playlists/([^/?]+)"
    subcategory = "api-playlists"

    def __init__(self, match):
        super().__init__(match)
        self.playlist_id = match.group(1)

    def items(self):
        resp = self.request(self.url)
        for item in (videos := resp.json().get("videos", [])):
            yield Message.Queue, f"http://www.youtube.com/watch?v={item['videoId']}", {}
        if videos:
            page = get_page_query(self.url)
            next_page = int(page) + 1 if page is not None else 2
            yield Message.Queue, get_api_playlists_url(
                self.playlist_id, str(next_page)
            ), {}
