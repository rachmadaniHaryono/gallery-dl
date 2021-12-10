#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json

from .common import GalleryExtractor, get_soup

BASE_PATTERN = r"(https?://)?(www.)?duga.jp"

import collections


class DugaPpvExtractor(GalleryExtractor):
    category = "duga"
    subcategory = "ppv"
    pattern = BASE_PATTERN + r"/ppv/(\w+-\d+)"

    def __init__(self, match):
        super().__init__(match)
        self.gallery_id = match.group(3)
        self.gallery_url = "https://duga.jp/ppv/{}/?action=imagesurl".format(
            self.gallery_id
        )

    def metadata(self, page):
        self.log.debug(f"page not accessed on metadata, {page}")
        soup = get_soup(
            self.request("https://duga.jp/ppv/{}/".format(self.gallery_id)).content
        )
        data = collections.defaultdict(list)
        if (html_tag := soup.select_one("h1.title")) and (tag := html_tag.text.strip()):
            data["title"].append(tag)
        tags = set()
        for row in soup.select("table.infomation tr"):
            header = ""
            if html_tag := row.select_one("th"):
                header = html_tag.text.strip()
            row_text = ""
            if html_tag := row.select_one("td"):
                row_text = html_tag.text
            a_texts = [a_tag.text.strip() for a_tag in row.select("td a")]
            if a_texts:
                for a_text in a_texts:
                    tags.add(f"{header}:{a_text}" if header else a_text)
            elif row_text:
                tags.add(f"{header}:{row_text}" if header else row_text)
        for tag in tags:
            data["category_"].append(tag)
        return data

    def images(self, page):
        json_data = json.loads(page)
        for item in json_data.get("digesturl", []):
            num = int(item.get("no"))
            if url := item.get("image"):
                yield url, {"num": num if num else None}
        if url := json_data.get("jacketurl"):
            yield url, {"num": None}
