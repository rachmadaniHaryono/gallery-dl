#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
from urllib import parse

import bs4
import requests

from .common import Extractor, Message

BASE_PATTERN = r"(?:https?://)?" r"bi-girl" r"\.net"


class BiGirlExtractor(Extractor):
    category = "bi-girl"

    def __init__(self, match):
        super().__init__(match)
        self.exclude_external_netloc = self.config("exclude_external_netloc", [])
        self.exclude_external_regex = self.config("exclude_external_regex", [])


class BiGirlSearchImageExtractor(BiGirlExtractor):
    pattern = BASE_PATTERN + r"/search-images(\?category=^[&]+)?"
    subcategory = "search-image"

    def items(self):
        try:
            resp: requests.models.Response = self.request(self.url)
            soup = bs4.BeautifulSoup(resp.content)
            img_src = {
                src.strip()
                for x in soup.find_all("img")
                if (src := x.get("src")) and src.strip()
            }
            a_href = {
                href.strip()
                for x in soup.find_all("a")
                if (href := x.get("href")) and href.strip()
            }
            for item, msg in [(a_href, Message.Queue), (img_src, Message.Url)]:
                url: str
                for url in item:
                    if url.startswith("//"):
                        url = "https:" + url
                    p_url = parse.urlparse(url)
                    if p_url.netloc in self.exclude_external_netloc:
                        self.log.debug("exclude netloc,%s", url)
                        continue
                    if self.exclude_external_regex and any(
                        re.match(x, url) for x in self.exclude_external_regex
                    ):
                        self.log.debug("exclude regex,%s", url)
                        continue
                    if p_url.netloc == "pics.dmm.co.jp" and msg == Message.Url:
                        yield Message.Queue, url, {}
                    else:
                        yield msg, url, {}
        except Exception as err:
            raise err
