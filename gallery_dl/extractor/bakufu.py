#!/usr/bin/env python
# -*- coding: utf-8 -*-
import collections
import os
import re
import typing as T
from urllib import parse

from .. import text
from .common import Extractor, GalleryExtractor, Message, get_soup

BASE_PATTERN = r"(?:https?://)?bakufu.jp"


class BakufuExtractor(Extractor):
    category = "bakufu"

    def __init__(self, match):
        super().__init__(match)
        self.exclude_external_netloc = self.config("exclude_external_netloc", [])
        self.exclude_external_regex = self.config("exclude_external_regex", [])


def replace_url(inp: str) -> T.Optional[str]:
    patt = r"(wp-content/uploads/[^/]+/[^/]+/\w+)-(\d+x\d+|scaled)(\..*)"
    if (
        new_url := re.sub(patt, lambda x: x.group(1) + x.group(3), inp)
    ) and new_url != inp:
        return new_url


class BakufuWpContentsExtractor(BakufuExtractor):
    subcategory = "wp-contents"
    pattern = BASE_PATTERN + r"/wp-content/uploads/"

    def items(self):
        yield Message.Url, self.url, {}
        if (new_url := replace_url(self.url)) and new_url != self.url:
            yield Message.Url, new_url, {}


def get_url_msg(soup):
    for html_tags, msg, attr in [
        (soup.select("a"), Message.Queue, "href"),
        (soup.select("img"), Message.Queue, "src"),
    ]:
        for html_tag in html_tags:
            yield html_tag.get(attr), msg


class BakufuCategoryExtractor(BakufuExtractor):
    subcategory = "category"
    pattern = BASE_PATTERN + r"/archives/category/.+"

    def items(self):
        soup = get_soup(self.request(self.url).content)
        s_url_netloc = parse.urlparse(self.url).netloc
        url_msg = list(get_url_msg(soup))
        for html_tag in soup.select("article h1.entry-title a"):
            if (val := html_tag.get("href")) and isinstance(val, list):
                for item in val:
                    url_msg.append((item, Message.Queue))
            elif isinstance(val, str):
                url_msg.append((val, Message.Queue))
            else:
                self.log.debug(f"unknown href value, {val}")
        for url, msg in url_msg:
            if url.startswith("//"):
                url = "https:" + url
            elif url.startswith("/"):
                url = parse.urljoin(self.url, url)
            p_url = parse.urlparse(url)
            cont = False

            for cond, dbg_msg in [
                (
                    lambda: p_url.netloc == s_url_netloc,
                    "recursive netloc,%s",
                ),
                (
                    lambda: p_url.netloc in self.exclude_external_netloc,
                    "exclude netloc,%s",
                ),
                (
                    lambda: self.exclude_external_regex
                    and any(re.match(x, url) for x in self.exclude_external_regex),
                    "exclude regex,%s",
                ),
            ]:
                if cond():
                    self.log.debug(dbg_msg, url)
                    cont = True
                    break
            if cont:
                continue
            if (
                p_url.netloc in ("img.sokmil.com", "pics.dmm.co.jp")
                and msg == Message.Url
            ):
                yield Message.Queue, url, {}
            elif (
                msg == Message.Url
                and p_url.netloc == "img.bakufu.jp"
                and (new_url := replace_url(url))
                and new_url != url
            ):
                yield Message.Url, new_url, {}
            else:
                yield msg, url, {}


class BakufuGalleryExtractor(BakufuExtractor, GalleryExtractor):
    pattern = BASE_PATTERN + r"(/archives/\d+)"
    root = "http://bakufu.jp"

    def init_soup(self, page=None):
        if not hasattr(self, "soup"):
            if page is None:
                raise ValueError("Empty page")
            self.soup = get_soup(page)
        return self.soup

    def items(self):
        try:
            yield from super().items()
            s_url_netloc = parse.urlparse(self.url).netloc
            for url, msg in get_url_msg(self.init_soup()):
                if url.startswith("//"):
                    url = "https:" + url
                elif url.startswith("/"):
                    url = parse.urljoin(self.url, url)
                p_url = parse.urlparse(url)
                cont = False
                for cond, dbg_msg in [
                    (
                        lambda: p_url.netloc == s_url_netloc,
                        "recursive netloc,%s",
                    ),
                    (
                        lambda: p_url.netloc in self.exclude_external_netloc,
                        "exclude netloc,%s",
                    ),
                    (
                        lambda: self.exclude_external_regex
                        and any(re.match(x, url) for x in self.exclude_external_regex),
                        "exclude regex,%s",
                    ),
                    (lambda: url in self.main_img_urls, "match main img urls,%s"),
                ]:
                    if cond():
                        self.log.debug(dbg_msg, url)
                        cont = True
                        break
                if cont:
                    continue
                if (
                    p_url.netloc in ("img.sokmil.com", "pics.dmm.co.jp")
                    and msg == Message.Url
                ):
                    yield Message.Queue, url, {}
                elif (
                    msg == Message.Url
                    and p_url.netloc == "img.bakufu.jp"
                    and (new_url := replace_url(url))
                    and new_url != url
                ):
                    if new_url in self.main_img_urls:
                        self.log.debug("new url match main img urls,%s", url)
                    else:
                        yield Message.Url, new_url, {}
                else:
                    yield msg, url, {}
        except Exception as err:
            raise err

    def metadata(self, page: str) -> T.Dict[str, T.Any]:
        """Return a dict with general metadata"""
        soup = self.init_soup(page)
        data = collections.defaultdict(list)
        for html_tag in soup.select("footer.entry-meta a"):
            data["category_"].append(html_tag.text)
        if html_tag := soup.select_one("h1.entry-title"):
            data["title"].append(html_tag.text.strip())
        return data

    def images(self, page: str):
        soup = self.init_soup(page)
        main_img_urls = []

        def update_data(data, url):
            basename = os.path.splitext(os.path.basename(parse.urlparse(url).path))[0]
            if match := re.match(r".*_(\d+)(-scaled)?", basename):
                data["num"] = int(match.group(1))
            return data

        for img_tag in soup.select("div.entry-content a img"):
            if (
                img_tag.parent
                and (href := img_tag.parent.get("href"))
                and href not in main_img_urls
            ):
                if isinstance(href, list):
                    self.log.warning("unexpected list, %s", href)
                    continue
                main_img_urls.append(href)
                if new_url := replace_url(href):
                    main_img_urls.append(new_url)
                    yield new_url, update_data(text.nameext_from_url(new_url), new_url)
                else:
                    yield href, update_data(text.nameext_from_url(href), href)
        self.main_img_urls = main_img_urls
