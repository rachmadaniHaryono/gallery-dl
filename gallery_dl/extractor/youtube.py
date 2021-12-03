#!/usr/bin/env python
# -*- coding: utf-8 -*-
from urllib import parse

from . import invidious
from .common import Extractor, Message

BASE_PATTERN = r"(?:https?://)?(www.)?youtube.com"


class YoutubeExtractor(Extractor):
    category = "youtube"


class YoutubeWatchExtractor(YoutubeExtractor):
    subcategory = "watch"
    pattern = BASE_PATTERN + r"/watch\?"

    def items(self):
        yield Message.Url, self.url, {}
        if pl_id := dict(parse.parse_qsl(parse.urlparse(self.url).query)).get("list"):
            yield Message.Queue, invidious.get_api_playlists_url(pl_id), {}


class YoutubeChannelExtractor(Extractor):
    subcategory = "channel"
    pattern = BASE_PATTERN + r"/c(hannel)?/.+"

    def items(self):
        p = parse.urlparse(self.url)
        if new_url := parse.ParseResult(
            **dict(p._asdict(), netloc=invidious.BASE_DOMAIN, scheme="http")
        ).geturl():
            resp = self.request(new_url)
            yield Message.Queue, resp.url, {}


class YoutubeRedirectExtractor(YoutubeExtractor):
    pattern = BASE_PATTERN + r"/redirect\?"
    subcategory = "redirect"

    def items(self):
        if url := dict(parse.parse_qsl(parse.urlparse(self.url).query)).get("q"):
            yield Message.Queue, url, {}


class Youtu_beExtractor(YoutubeExtractor):
    category = "youtu_be"
    pattern = r"(?:https?://)?youtu.be/[^/?]+"

    def items(self):
        yield Message.Url, self.url, {}
