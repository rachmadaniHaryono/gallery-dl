#!/usr/bin/env python
# -*- coding: utf-8 -*-
import more_itertools

from .common import Extractor, Message, get_soup


class TExtractor(Extractor):
    category = "t"
    pattern = r"(?:https?://)?t.co/\w+"

    def items(self):
        soup = get_soup(self.request(self.url).content)
        new_url = ""
        if html_tag := soup.select_one("meta"):
            attr_val = html_tag.get("content")
            if isinstance(attr_val, str):
                new_url = more_itertools.nth(attr_val.split("URL="), 1, "")
            else:
                self.log.warning(f"unknown value of attr_val, {attr_val}")
        if new_url and new_url != self.url:
            yield Message.Queue, new_url, {}
