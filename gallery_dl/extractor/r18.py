#!/usr/bin/env python
# -*- coding: utf-8 -*-

#  https://www.r18.com/videos/vod/movies/detail/-/id=kmtd00001/

import json
import typing as T

from .common import Extractor, GalleryExtractor

BASE_PATTERN = r"(https?://)?(www.)?r18.com"

import collections


class R18Extractor(Extractor):
    category = "r18"


class R18ApiExtractor(R18Extractor, GalleryExtractor):
    subcategory = "api"
    pattern = BASE_PATTERN + r"/api/v4f/contents/([^?]+)"

    def __init__(self, match):
        super().__init__(match)
        self.gallery_id = match.group(1)
        self.gallery_url = self.url

    def init_json_data(self, page):
        if not hasattr(self, "json_data"):
            self.json_data: T.Dict[str, T.Any] = json.loads(page).get("data", {})
        return self.json_data

    def metadata(self, page):
        data = collections.defaultdict(list)
        try:
            json_data = self.init_json_data(page)
            # tag with list of dict with key name, example: [{'name': name}, ...]
            if item := json_data.get("channels"):
                p_items = []
                if isinstance(item, dict):
                    p_items.append(item)
                elif isinstance(item, list):
                    p_items.extend(item)
                else:
                    self.log.warning("unknown channels value, %s", item)
                if p_items:
                    for subitem in p_items:
                        if subtag := subitem.get("name"):
                            data["category_"].append("channel:{}".format(subtag))
            for key, fmt in (
                ("actresses", "person:{}"),
                ("categories", "{}"),
            ):
                for item in json_data.get(key, []):
                    if subtag := item.get("name"):
                        data["category_"].append(fmt.format(subtag))
            for namespace, key, fmt in (
                ("category_", "content_id", "{key}:{subtag}"),
                ("category_", "director", "{key}:{subtag}"),
                ("category_", "dvd_id", "{key}:{subtag}"),
                ("title", "title", "{subtag}"),
            ):
                if subtag := json_data.get(key):
                    data[namespace].append(fmt.format(subtag=subtag, key=key))
            for key in ("maker", "label", "series"):
                if (j_subdata := json_data.get(key, {})) and (
                    subtag := j_subdata.get("name")
                ):
                    data["category_"].append(f"{key}:{subtag}")
            if (value := json_data.get("release_date")) and (
                subtag := value.split(" ", 1)[0]
            ):
                data["category_"].append(f"release_date:{subtag}")
            for key, value in filter(
                lambda x: x[0]
                not in (
                    (
                        "actresses",
                        "categories",
                        "channels",
                        "content_id",
                        "director",
                        "dvd_id",
                        "gallery",
                        "images",
                        "label",
                        "maker",
                        "release_date",
                        "series",
                        "title",
                    )
                ),
                json_data.items(),
            ):
                self.log.debug("unused, %s:%s", key, value)
        except Exception as err:
            raise err
        return data

    def images(self, page):
        json_data = self.init_json_data(page)
        for item in json_data.get("gallery", []):
            yield item.get("large"), {}
        if url := json_data.get("images", {}).get("jacket_image", {}).get("large"):
            yield url, {"num": None}


class R18GalleryExtractor(R18ApiExtractor):
    subcategory = "gallery"
    pattern = BASE_PATTERN + r"/videos/vod/movies/detail/-/id=([^/?]+)"

    def __init__(self, match):
        super().__init__(match)
        self.gallery_id = match.group(3)
        self.url = "https://www.r18.com/api/v4f/contents/{}?lang=en&unit=USD".format(
            match.group(3)
        )
        self.gallery_url = self.url
