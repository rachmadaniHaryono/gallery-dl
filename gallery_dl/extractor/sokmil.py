#!/usr/bin/env python
# -*- coding: utf-8 -*-


import re
import typing as T
from urllib import parse

import more_itertools

from .common import Extractor, Message, get_soup

BASE_PATTERN = r"(?:https?://)?(www.)?sokmil.com"


class SokmilExtractor(Extractor):
    category = "sokmil"

    def __init__(self, match):
        super().__init__(match)
        self.exclude_external_netloc = self.config("exclude_external_netloc", [])


def replace_url(inp: str) -> T.Optional[str]:
    # these are similar
    #  https://img.sokmil.com/image/product/pe_vod0058_01_T1515126604.jpg
    #  https://img.sokmil.com/image/product/pef_vod0058_01_150x_T1515126604.jpg
    #  https://img.sokmil.com/image/product/pef_vod0058_01_T1515126604.jpg
    # but only following url is thumbnail
    #  https://img.sokmil.com/image/product/pef_vod0058_01_150x_T1515126604.jpg
    patt = r"(/image/capture/)cs(_\w+\d+_\d+_\w+\d+\.\w+)"
    if (
        new_url := re.sub(patt, lambda x: x.group(1) + "ol" + x.group(2), inp)
    ) and new_url != inp:
        return new_url
    patt = r"(/image/product/\w+_\w+\d+_\d+_)\d+\w+(\d+)?_(\w+\d+\.\w+)"
    if (
        new_url := re.sub(patt, lambda x: x.group(1) + x.group(3), inp)
    ) and new_url != inp:
        return new_url


class SokmilImgExtractor(SokmilExtractor):
    pattern = r"(?:https?://)?img.sokmil.com"
    subcategory = "img"

    def items(self):
        yield Message.Url, self.url, {}
        if (new_url := replace_url(self.url)) and new_url != self.url:
            yield Message.Url, new_url, {}


class SokmilPostExtractor(SokmilExtractor):
    pattern = BASE_PATTERN + r"/(av|idol)/_item/item\d+.htm(\?.*)?"
    subcategory = "post"

    def items(self):
        try:
            #  img_urls
            resp = self.request(self.url)
            soup = get_soup(resp.content)
            img_urls = set()
            for html_tag in soup.select("li.thumbnail-item a"):
                if url := html_tag.get("href"):
                    if isinstance(url, list):
                        raise ValueError(f"html tag return multiple href,{url}")
                    new_url = replace_url(url)
                    img_urls.add(new_url if new_url else url)
            if html_tag := soup.select_one("div.jacket a > img.jacket-img"):
                img_urls.add(html_tag.get("src"))
                img_urls.add(html_tag.get("content"))
                if html_tag.parent:
                    img_urls.add(html_tag.parent.get("href"))
            for html_tag in soup.select(
                "div.img-area span.badge-area-wrapper img.img.jacket-img"
            ):
                src = html_tag.get("src")
                if isinstance(src, list):
                    raise ValueError(f"html_tag return multiple src,{src}")
                if src:
                    img_urls.add(new_url if (new_url := replace_url(src)) else src)
                if srcset := html_tag.get("srcset"):
                    if isinstance(srcset, list):
                        raise ValueError(f"html_tag return multiple srcset,{srcset}")
                    for item in srcset.split(", "):
                        parts = item.rsplit(" ", 1)
                        self.log.debug(f"removing,{parts[1]} from {item}")
                        img_urls.add(
                            new_url if (new_url := replace_url(parts[0])) else parts[0]
                        )
            if html_tag := soup.select_one("div.player-thumb-area img"):
                img_urls.add(html_tag.get("src"))
            # tags
            data = {}
            rows = [x for x in soup.select("div.info-area dl.product-info")]
            rows_data = []
            for row in rows:
                row_item: T.List[T.Union[str, None, T.List[str]]] = [
                    dt.text if (dt := row.select_one("dt")) else None
                ]
                if dd := row.select_one("dd"):
                    row_item.append(re.sub(r"\s+", " ", dd.text.strip()))
                    sub_item = []
                    for x in dd.select("a"):
                        sub_item.append(x.text)
                    if sub_item:
                        row_item.append(sub_item)
                rows_data.append(row_item)
                pass
            category = []
            for row in rows_data:
                if item := more_itertools.nth(row, 2, None):
                    for subitem in item:
                        category.append(":".join([row[0], subitem]))
                else:
                    category.append(":".join([row[0], row[1]]))
            if category:
                data["category_"] = category
            if html_tag := soup.select_one("h1"):
                data["title"] = [html_tag.text]
            for url in img_urls:
                yield Message.Url, url, data
            # other image urls
            new_img_urls = set()
            for html_tag in soup.select("img"):
                src = html_tag.get("src")
                if isinstance(src, list):
                    raise ValueError(f"html_tag return multiple src,{src}")
                new_src = replace_url(src) if src else None
                url = new_src if new_src else src
                if not url:
                    continue
                if url.startswith(("data:image", "/analyze/")):
                    continue
                if url not in img_urls:
                    new_img_urls.add(url)
            for url in new_img_urls:
                if parse.urlparse(url).netloc in self.exclude_external_netloc:
                    self.log.debug("exclude netloc,%s", url)
                else:
                    yield Message.Url, url, {}
        except Exception as err:
            raise err
