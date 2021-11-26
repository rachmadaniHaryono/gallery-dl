#!/usr/bin/env python
# -*- coding: utf-8 -*-
from .common import Extractor, Message


class YoutubeExtractor(Extractor):
    category = "youtube"
    pattern = r"(?:https?://)?(www.)?youtube.com/(channel/|watch?)"

    def items(self):
        yield Message.Url, self.url, {}


class Youtu_beExtractor(YoutubeExtractor):
    category = "youtu_be"
    pattern = r"(?:https?://)?youtu.be/[^/?]+"
