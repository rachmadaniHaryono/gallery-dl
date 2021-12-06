#!/usr/bin/env python
# -*- coding: utf-8 -*-
from urllib import parse

from .common import Extractor, Message


class DuckduckgoExtractor(Extractor):
    category = "duckduckgo"


class DuckduckgoExternalExtractor(DuckduckgoExtractor):
    subcategory = "external"
    pattern = r"(https?://)?external-content.duckduckgo.com/iu/\?"

    def items(self):
        if url := dict(parse.parse_qsl(parse.urlparse(self.url).query)).get("u"):
            yield Message.Queue, url, {}
