#!/usr/bin/env python
# -*- coding: utf-8 -*-
import collections
import re
import typing as T
from urllib import parse

from .common import Extractor, GalleryExtractor, Message, get_soup

BASE_PATTERN = "https?://erogazou-onaneta.com"


class ErogazouOnanetaExtractor(Extractor):
    category = "erogazou-onaneta"


class ErogazouOnanetaUrlExtractor(ErogazouOnanetaExtractor):
    pattern = BASE_PATTERN + r"(/wp-content/uploads/.*)-\d*x\d*(\..{3,4})"
    subcategory = "url"

    def __init__(self, match):
        super().__init__(match)
        self.new_url = parse.urljoin(self.url, match.group(1) + match.group(2))

    def items(self):
        yield Message.Url, self.new_url, {}


class ErogazouOnanetaGalleryExtractor(ErogazouOnanetaExtractor, GalleryExtractor):
    pattern = BASE_PATTERN + r"/[^/]+/(\d+)\.html"

    def __init__(self, match):
        super().__init__(match)
        self.gallery_id = match.group(1)
        self.gallery_url = self.url
        self.main_img_urls = set()

    def init_soup(self, page=None):
        if not hasattr(self, "soup"):
            if page is None:
                raise ValueError("Empty page")
            self.soup = get_soup(page)
        return self.soup

    def items(self):
        yield from super().items()
        soup = self.init_soup()
        for html_tag in soup.select("img"):
            if not (src := html_tag.get("src")):
                continue
            urls = [src] if isinstance(src, str) else src
            for url in [x for x in urls if x not in self.main_img_urls]:
                msg = (
                    Message.Queue
                    if re.match(ErogazouOnanetaUrlExtractor.pattern, url)
                    else Message.Url
                )
                yield msg, url, {}

    def images(self, page: str) -> T.Iterator[T.Tuple[str, T.Dict[str, T.Any]]]:
        soup = self.init_soup(page)
        for html_tag in soup.select("section.entry-content a > img"):
            if not (src := html_tag.get("src")):
                continue
            urls = [src] if isinstance(src, str) else src
            if (
                (parent_tag := html_tag.parent)
                and (parent_url := parent_tag.get("href"))
                and parent_url not in urls
            ):
                self.log.warning(
                    "different parent url, parent: %s\nurls:\n%s",
                    parent_url,
                    "\n".join(urls),
                )
            for url in urls:
                yield url, {"num": None}
                self.main_img_urls.add(url)

    def metadata(self, page: str) -> T.Dict[str, T.Any]:
        soup = self.init_soup(page)
        data = collections.defaultdict(list)
        if (html_tag := soup.select_one("h1.entry-title")) and (
            subtag := html_tag.text
        ):
            data["thread"].append(subtag)
        for html_tag in [x for x in soup.select("footer.article-footer a") if x.text]:
            data["category_"].append(html_tag.text)
        return data
