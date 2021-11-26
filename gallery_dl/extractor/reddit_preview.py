#!/usr/bin/env python
# -*- coding: utf-8 -*-
from .common import Extractor, Message

BASE_PATTERN = r"(?:https?://)?preview.redd.it"


class Preview_redditExtractor(Extractor):
    category = "preview_reddit"
    pattern = BASE_PATTERN + r"/([^.]+\.[^?]+)"

    def __init__(self, match):
        super().__init__(match)
        self.basename = match.group(1)

    def items(self):
        yield Message.Url, self.url, {}
        yield Message.Url, "https://i.redd.it/{}".format(self.basename), {}
