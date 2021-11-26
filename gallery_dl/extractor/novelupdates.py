#!/usr/bin/env python
# -*- coding: utf-8 -*-
import collections

from .common import Extractor, Message, get_soup


class NovelupdatesExtractor(Extractor):
    category = "novelupdates"
    pattern = r"(?:https?://)?(www.)?novelupdates.com/series/"

    def items(self):
        soup = get_soup(self.request(self.url).content)
        data = collections.defaultdict(list)
        for selector, namespace in (
            ("div.seriestitlenu", "series"),
            ("div#showtype", "category"),
        ):
            if (html_tag := soup.select_one(selector)) and html_tag.text:
                data[namespace].append(html_tag.text.strip())
        for selector, prefix in (
            ("div#seriesgenre a", "genre:"),
            ("div#showartists a", "artist:"),
            ("div#showauthors a", "author:"),
            ("div#showlang a", "language:"),
            ("div#showpublisher a", "original publisher:"),
            ("div#showtags a", ""),
        ):
            if html_tags := soup.select(selector):
                for html_tag in html_tags:
                    data["category_"].append(prefix + html_tag.text)
        if (html_tag := soup.select_one("div#editassociated")) and html_tag.text:
            for item in html_tag.get_text(separator="\n").splitlines():
                if item:
                    data["description"].append("associated name:" + item)
        if (html_tag := soup.select_one("div.seriesimg img")) and (
            src := html_tag.get("src", None)
        ):
            yield Message.Url, src, data
