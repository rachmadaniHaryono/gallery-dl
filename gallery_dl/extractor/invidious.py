#!/usr/bin/env python
# -*- coding: utf-8 -*-
import typing as T
from urllib import parse

from .common import Extractor, Message

BASE_PATTERN = r"(?:https?://)?localhost:3000"


class InvidiousExtractor(Extractor):
    category = "invidious"


def get_api_channel_url(channel_id: str, page: T.Union[str, int] = None) -> str:
    new_url = "http://localhost:3000/api/v1/channels/videos/{}".format(channel_id)
    if page:
        new_url = (
            parse.urlparse(new_url)
            ._replace(query=parse.urlencode({"page": page}))
            .geturl()
        )
    return new_url


class InvidiousChannelExtractor(InvidiousExtractor):
    pattern = BASE_PATTERN + r"/channel/([^/?]+)(\?page=(\d+))?"
    subcategory = "channel"

    def __init__(self, match):
        super().__init__(match)
        self.channel_id = match.group(1)
        self.page = match.group(3)

    def items(self):
        yield Message.Queue, get_api_channel_url(self.channel_id, self.page), {}


class InvidiousApiChannelsExtractor(InvidiousExtractor):
    pattern = BASE_PATTERN + r"/api/v1/channels/((([^/?])+/videos)|(videos/([^/?]+)))"
    subcategory = "api-channels"

    def __init__(self, match):
        super().__init__(match)
        self.channel_id = match.group(2) or match.group(5)

    def items(self):
        resp = self.request(self.url)
        new_urls = {
            f"http://localhost:3000/watch?v={item['videoId']}" for item in resp.json()
        }
        for item in new_urls:
            yield Message.Url, item, {}
        p_url = parse.urlparse(self.url)
        if new_urls:
            page = None
            if p_url.query:
                page = parse.parse_qs(p_url.query).get("page", [None])[0]
            yield Message.Queue, get_api_channel_url(
                self.channel_id, int(page) + 1 if page is not None else 2
            ), {}
        else:
            self.log.debug("no url,%s", self.url)
