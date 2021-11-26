#!/usr/bin/env python
# -*- coding: utf-8 -*-
from .common import Extractor, Message

BASE_PATTERN = r"(?:https?://)?click.dtiserv2.com"


class Dtiserv2Extractor(Extractor):
    category = "dtiserv2"
    pattern = BASE_PATTERN

    def items(self):
        resp = self.request(self.url)
        yield Message.Queue, resp.url, {}
