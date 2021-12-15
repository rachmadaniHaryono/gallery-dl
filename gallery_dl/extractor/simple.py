#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import typing as T

from .common import Extractor, Message


class SimpleExtractor(Extractor):
    pattern = r"http://example.com/(\d).html"
    send_old_data = False
    queue_data: T.Optional[T.List[str]] = None
    url_data: T.Optional[T.List[str]] = None

    def items(self):
        if self.send_old_data:
            yield Message.Url, self.url, {}
        match = (
            re.match(self.pattern, self.url)
            if isinstance(self.pattern, str)
            else self.pattern.match(self.url)
        )
        if not match:
            return
        for fmts, msg in (
            (self.queue_data, Message.Queue),
            (self.url_data, Message.Url),
        ):
            if not fmts:
                continue
            for fmt in fmts:
                yield msg, fmt.format(*match.groups()), {}
