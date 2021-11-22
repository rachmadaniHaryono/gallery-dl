#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import typing as T
from urllib import parse

from .common import Extractor, Message, get_soup


class DmmExtractor(Extractor):
    category = "dmm"


class DmmAlExtractor(DmmExtractor):
    pattern = r"(?:https?://)?al\.dmm.co.jp/\?lurl=https%3A%2F%2Fwww.dmm.co.jp%2Fdigital%2Fvideo.*%2F-%2Fdetail%2F%3D%2Fcid%3D.+"
    subcategory = "al"

    def items(self):
        yield Message.Queue, parse.parse_qs(parse.urlparse(self.url).query)["lurl"][
            0
        ], {}


def replace_url(inp: str) -> T.Optional[str]:
    netloc = parse.urlparse(inp).netloc
    if netloc in ("pics.dmm.co.jp"):
        patt = r"(/digital/+amateur/+\w+\d+/+\w+\d+\w+)s(-\d+\.[^/.]+)(?:[?#].*)?$"
        if (
            new_url := re.sub(patt, lambda x: x.group(1) + "p" + x.group(2), inp)
        ) and new_url != inp:
            return new_url
    if netloc in ("pics.r18.com", "pics.dmm.co.jp", "pics.avdmm.top"):
        patt = r"(/digital/+video/+(h_)?[0-9a-z]+[0-9]+/+(h_)?[0-9a-z]+[0-9]+)(-[0-9]+\.[^/.]+)(?:[?#].*)?$"
        if (
            new_url := re.sub(patt, lambda x: x.group(1) + "jp" + x.group(4), inp)
        ) and new_url != inp:
            return new_url

    if netloc in ("pics.dmm.co.jp", "pics.dmm.com"):
        patt = r"s(\.[^/.]*)$"
        if new_url := re.sub(patt, lambda x: "l" + x.group(1), inp):  # type: ignore
            return new_url


class DmmPicsExtractor(DmmExtractor):
    pattern = r"(?:https?://)?pics.(avdmm.top|dmm.co.jp|dmm.com|r18.com)/"
    subcategory = "pics"

    def items(self):
        yield Message.Url, self.url, {}
        if (new_url := replace_url(self.url)) and new_url != self.url:
            yield Message.Url, new_url, {}


class DmmDigitalExtractor(DmmExtractor):
    pattern = r"(?:https?://)?(www.)?dmm.co.jp/((digital/video[^/]*|mono/dvd)/-/detail/=/cid=([^/]+)/?|)"
    subcategory = "digital"

    def __init__(self, match):
        super().__init__(match)
        self.cid = match.groups()[1]

    def items(self):
        soup = get_soup(self.request(self.url).content)  # type: ignore
        links = [
            href
            for x in soup.find_all("a")
            if (href := x.get("href")) and "dmm.co.jp/age_check/=/declared=yes/" in href
        ]
        if links:
            self.log.debug("new request,%s", links[0])
            soup = get_soup(self.request(links[0]).content)  # type: ignore
        rows = [x for x in soup.select("div.page-detail table tr")]
        rows_data = []
        for row in rows:
            cells = row.select("td")
            if 1 < len(cells) < 3:
                rows_data.append(
                    [
                        cells[0].text.strip(),
                        [x.text.strip() for x in cells[1].select("a")],
                        cells[1].text.strip(),
                        len(cells),
                    ]
                )
        data = {}
        if (subtag := soup.select_one("h1#title")) and subtag.text:
            data["title"] = [subtag.text]
        category = []
        for item in rows_data:
            item0 = re.sub(r"\s+", " ", item[0]).replace("：", "")
            if item[1]:
                for val in item[1]:
                    category.append(":".join([item0, val]))
            else:
                category.append(":".join([item0, item[2]]))
        if category:
            data["category_"] = category
        urls = set()
        for src in [x.get("src") for x in soup.select("div#sample-image-block a img")]:
            new_url = replace_url(src)  # type:ignore
            if not new_url:
                new_url = src
            urls.add(new_url)
        img_url = None
        for css_path in [
            "div#sample-video.center a img",
            "div#sample-video.center img",
        ]:
            if html_tag := soup.select_one(css_path):
                img_url = html_tag.get("src")
                urls.add(img_url)
                break
        urls.add(soup.select_one("div#sample-video.center a").get("href"))  # type: ignore
        if img_url and (new_url := replace_url(img_url)):  # type: ignore
            urls.add(new_url)
        for url in urls:
            if not url.startswith("javascript:"):
                yield Message.Url, url, data
