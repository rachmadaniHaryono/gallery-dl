#!/usr/bin/env python
# -*- coding: utf-8 -*-
import itertools
import re
from urllib import parse

from .common import Extractor, Message, get_img_srcs_and_a_hrefs, get_soup


class DvdrevExtractor(Extractor):
    category = "dvdrev"
    pattern = r"(https?://)?dvdrev.com/blog-entry-(\d+).html"

    def init_soup(self, page):
        if not hasattr(self, "soup"):
            self.soup = get_soup(page)
        return self.soup

    def items(self):
        soup = get_soup(self.request(self.url).content)
        exclude_external_regex = self.config("exclude_external_regex", [])
        for html_tags, attr, msg in [
            (soup.select("a"), "href", Message.Queue),
            (soup.select("img"), "src", Message.Url),
        ]:
            for html_tag in html_tags:
                url: str = html_tag.get(attr)
                p_url = parse.urlparse(url)
                if url.startswith(("#", "/", "data:image/")):
                    self.log.debug(f"invalid start characters, {url}")
                    continue
                if p_url.netloc == "dvdrev.com":
                    self.log.debug(f"recursive url, {url}")
                    continue
                if p_url.netloc == "al.dmm.co.jp":
                    pass
                elif not p_url.path or p_url.path in ("/", "//"):
                    self.log.debug(f"no path, {url}")
                    continue

                # check exclude_external_regex
                skip_url = False
                for patt in exclude_external_regex:
                    if re.match(patt, url):
                        skip_url = True
                        break
                if skip_url:
                    continue

                yield msg, url, {}
