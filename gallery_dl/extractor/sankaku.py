# -*- coding: utf-8 -*-

# Copyright 2014-2020 Mike Fährmann
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.

"""Extractors for https://beta.sankakucomplex.com/"""

from .booru import BooruExtractor
from .. import text, exception
from ..cache import cache
import collections

BASE_PATTERN = r"(?:https?://)?(?:beta|chan)\.sankakucomplex\.com"


class SankakuExtractor(BooruExtractor):
    """Base class for sankaku channel extractors"""
    basecategory = "booru"
    category = "sankaku"
    filename_fmt = "{category}_{id}_{md5}.{extension}"
    cookiedomain = None
    per_page = 100
    _warning = True

    TAG_TYPES = {
        0: "general",
        1: "artist",
        2: "studio",
        3: "copyright",
        4: "character",
        5: "genre",
        6: "",
        7: "",
        8: "medium",
        9: "meta",
    }

    def _prepare_post(self, post, extended_tags=False):
        url = post["file_url"]
        if not url and self._warning:
            self.log.warning(
                "Login required to download 'contentious_content' posts")
            SankakuExtractor._warning = False
        if extended_tags:
            self._fetch_extended_tags(post)
        post["date"] = text.parse_timestamp(post["created_at"]["s"])
        post["tags"] = [tag["name"] for tag in post["tags"]]
        return url

    def _fetch_extended_tags(self, post):
        tags = collections.defaultdict(list)
        types = self.TAG_TYPES
        for tag in post["tags"]:
            tags[types[tag["type"]]].append(tag["name"])
        for key, value in tags.items():
            post["tags_" + key] = value


class SankakuTagExtractor(SankakuExtractor):
    """Extractor for images from chan.sankakucomplex.com by search-tags"""
    subcategory = "tag"
    directory_fmt = ("{category}", "{search_tags}")
    archive_fmt = "t_{search_tags}_{id}"
    pattern = BASE_PATTERN + r"/\?([^#]*)"
    test = (
        ("https://beta.sankakucomplex.com/?tags=bonocho", {
            "count": 5,
            "pattern": r"https://c?s\.sankakucomplex\.com/data/[^/]{2}/[^/]{2}"
                       r"/[^/]{32}\.\w+\?e=\d+&m=[^&#]+",
        }),
        # error on five or more tags
        ("https://chan.sankakucomplex.com/?tags=bonocho+a+b+c+d", {
            "options": (("username", None),),
            "exception": exception.StopExtraction,
        }),
        # match arbitrary query parameters
        ("https://chan.sankakucomplex.com"
         "/?tags=marie_rose&page=98&next=3874906&commit=Search"),
    )

    def __init__(self, match):
        SankakuExtractor.__init__(self, match)
        query = text.parse_query(match.group(1))
        self.tags = text.unquote(query.get("tags", "").replace("+", " "))

    def metadata(self):
        return {"search_tags": self.tags}

    def posts(self):
        return SankakuAPI(self).posts_keyset({"tags": self.tags})


class SankakuPoolExtractor(SankakuExtractor):
    """Extractor for image pools or books from chan.sankakucomplex.com"""
    subcategory = "pool"
    directory_fmt = ("{category}", "pool", "{pool[id]} {pool[name_en]}")
    archive_fmt = "p_{pool}_{id}"
    pattern = BASE_PATTERN + r"/(?:books|pool/show)/(\d+)"
    test = (
        ("https://beta.sankakucomplex.com/books/90", {
            "count": 5,
        }),
        ("https://chan.sankakucomplex.com/pool/show/90"),
    )

    def __init__(self, match):
        SankakuExtractor.__init__(self, match)
        self.pool_id = match.group(1)

    def metadata(self):
        pool = SankakuAPI(self).pools(self.pool_id)
        self._posts = pool.pop("posts")
        return {"pool": pool}

    def posts(self):
        return self._posts


class SankakuPostExtractor(SankakuExtractor):
    """Extractor for single images from chan.sankakucomplex.com"""
    subcategory = "post"
    archive_fmt = "{id}"
    pattern = BASE_PATTERN + r"/post/show/(\d+)"
    test = (
        ("https://beta.sankakucomplex.com/post/show/360451", {
            "content": "5e255713cbf0a8e0801dc423563c34d896bb9229",
            "options": (("tags", True),),
            "keyword": {
                "tags_artist": ["bonocho"],
                "tags_studio": ["dc_comics"],
                "tags_medium": ["sketch", "copyright_name"],
                "tags_copyright": list,
                "tags_character": list,
                "tags_general"  : list,
            },
        }),
        # 'contentious_content'
        ("https://beta.sankakucomplex.com/post/show/21418978", {
            "pattern": r"https://s\.sankakucomplex\.com"
                       r"/data/13/3c/133cda3bfde249c504284493903fb985\.jpg",
        }),
        ("https://chan.sankakucomplex.com/post/show/360451"),
    )

    def __init__(self, match):
        SankakuExtractor.__init__(self, match)
        self.post_id = match.group(1)

    def posts(self):
        return SankakuAPI(self).posts_keyset({"tags": "id:" + self.post_id})


class SankakuAPI():
    """Interface for the beta.sankakucomplex.com API"""

    def __init__(self, extractor):
        self.extractor = extractor
        self.headers = {"Accept": "application/vnd.sankaku.api+json;v=2"}

        self.username, self.password = self.extractor._get_auth_info()
        if not self.username:
            self.authenticate = lambda: None

    def pools(self, pool_id):
        return self._call("/pools/" + pool_id)

    def posts_keyset(self, params):
        return self._pagination("/posts/keyset", params)

    def authenticate(self):
        self.headers["Authorization"] = \
            _authenticate_impl(self.extractor, self.username, self.password)

    def _call(self, endpoint, params=None):
        url = "https://capi-v2.sankakucomplex.com" + endpoint
        for _ in range(5):
            self.authenticate()
            response = self.extractor.request(
                url, params=params, headers=self.headers, fatal=False)

            if response.status_code == 429:
                self.extractor.wait(
                    until=response.headers.get("X-RateLimit-Reset"))
                continue

            data = response.json()
            if not data.get("success", True):
                code = data.get("code")
                if code == "invalid_token":
                    _authenticate_impl.invalidate(self.username)
                    continue
                raise exception.StopExtraction(code)
            return data

    def _pagination(self, endpoint, params):
        params["lang"] = "en"
        params["limit"] = str(self.extractor.per_page)

        while True:
            data = self._call(endpoint, params)
            yield from data["data"]

            params["next"] = data["meta"]["next"]
            if not params["next"]:
                return
            if "page" in params:
                del params["page"]


@cache(maxage=365*24*3600, keyarg=2)
def _authenticate_impl(extr, username, password):
    extr.log.info("Logging in as %s", username)
    headers = {"Accept": "application/vnd.sankaku.api+json;v=2"}

    # get initial access_token
    url = "https://login.sankakucomplex.com/auth/token"
    data = {"login": username, "password": password}
    response = extr.request(
        url, method="POST", headers=headers, json=data, fatal=False)
    data = response.json()

    if response.status_code >= 400 or not data.get("success"):
        raise exception.AuthenticationError(data.get("error"))
    access_token = data["access_token"]

    # start openid auth
    url = "https://login.sankakucomplex.com/oidc/auth"
    params = {
        "response_type": "code",
        "scope"        : "openid",
        "client_id"    : "sankaku-web-app",
        "redirect_uri" : "https://beta.sankakucomplex.com/sso/callback",
        "state"        : "return_uri=https://beta.sankakucomplex.com/",
        "theme"        : "black",
        "lang"         : "undefined",
    }
    page = extr.request(url, params=params).text
    submit_url = text.extract(page, 'submitUrl = "', '"')[0]

    # get code from initial access_token
    url = "https://login.sankakucomplex.com" + submit_url
    data = {
        "accessToken": access_token,
        "nonce"      : "undefined",
    }
    response = extr.request(url, method="POST", data=data)
    query = text.parse_query(response.request.url.partition("?")[2])

    # get final access_token from code
    url = "https://capi-v2.sankakucomplex.com/sso/finalize?lang=en"
    data = {
        "code"        : query["code"],
        "client_id"   : "sankaku-web-app",
        "redirect_uri": "https://beta.sankakucomplex.com/sso/callback",
    }
    response = extr.request(
        url, method="POST", headers=headers, json=data, fatal=False)
    data = response.json()

    if response.status_code >= 400 or not data.get("success"):
        raise exception.AuthenticationError(data.get("error"))
    return "Bearer " + data["access_token"]
