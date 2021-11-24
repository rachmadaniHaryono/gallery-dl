#!/usr/bin/env python
# -*- coding: utf-8 -*-
import collections
import itertools
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


class BakufuGalleryExtractor(BakufuExtractor, GalleryExtractor):
    pattern = BASE_PATTERN + r"(/archives/\d+)"
    root = "http://bakufu.jp"

    def items(self):
        try:
            yield from super().items()
            soup = (
                self.soup
                if hasattr(self, "soup")
                else get_soup(self.request(self.url).content)
            )
            img_src = {
                src.strip()
                for x in soup.find_all("img")
                if (src := x.get("src")) and src.strip()
            }
            a_href = {
                href.strip()
                for x in soup.find_all("a")
                if (href := x.get("href")) and href.strip()
            }
            s_url_netloc = parse.urlparse(self.url).netloc
            list_product = lambda args: list(itertools.product(*args))
            for url, msg in [  # type: ignore
                *list_product((a_href, [Message.Queue])),
                *list_product((img_src, [Message.Url])),
            ]:
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
        soup = get_soup(page)
        if not hasattr(self, "soup"):
            self.soup = soup
        soup = self.soup
        data = collections.defaultdict(list)
        for html_tag in soup.select("footer.entry-meta a"):
            data["category_"].append(html_tag.text)
        if html_tag := soup.select_one("h1.entry-title"):
            data["title"].append(html_tag.text.strip())
        return data

    def images(self, page: str):
        soup = get_soup(page)
        if not hasattr(self, "soup"):
            self.soup = soup
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
