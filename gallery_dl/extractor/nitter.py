#!/usr/bin/env python
# -*- coding: utf-8 -*-
import collections
import logging
import re
import typing as T
from urllib import parse

try:
    from nitter_scraper import schema, tweets
except ImportError:
    schema = None
    tweets = None
from requests_html import HTMLSession

from .common import Extractor, Message

BASE_PATTERN = r"(?:https?://)?localhost:8080"


def pagination_parser(timeline, url) -> str:
    next_page = list(timeline.find(".show-more")[-1].links)[0]
    return parse.urlparse(url)._replace(query=parse.urlparse(next_page).query).geturl()


def get_tweets(
    url: str,
    session: HTMLSession,
    pages: int = 25,
    break_on_tweet_id: T.Optional[int] = None,
    log: T.Optional[logging.Logger] = None,
) -> T.Generator[T.Union[T.Dict[str, schema.Tweet], T.Dict[str, str]], None, None]:
    """Gets the target users tweets

    This is modified from nitter_scraper.tweets.get_tweets.

    Args:
        pages: Max number of pages to lookback starting from the latest tweet.
        break_on_tweet_id: Gives the ability to break out of a loop if a tweets id is found.

    Yields:
        Tweet Objects
    """

    while pages > 0:
        next_url = url
        response = session.get(url)
        timeline = None
        if response.status_code == 200:
            timeline_items = (
                timeline.find(".timeline-item")
                if (timeline := tweets.timeline_parser(response.html))
                else response.html.find(".timeline-item")
            )  # type:ignore
            if timeline_items:
                for item in timeline_items:
                    if "show-more" in item.attrs["class"]:
                        continue

                    if not item.find(".tweet-link", first=True):
                        continue
                    tweet_data = tweets.parse_tweet(item)
                    tweet = schema.Tweet.from_dict(tweet_data)

                    if tweet.tweet_id == break_on_tweet_id:
                        pages = 0
                        break

                    yield {"tweet": tweet}

        prev_url = next_url
        next_url = pagination_parser(timeline, url) if timeline else None
        if next_url:
            yield {"next_url": next_url}
        elif log:
            log.warning(f"no next url, {prev_url}")
        pages -= 1


def replace_url(inp: str) -> T.Optional[str]:
    netloc = parse.urlparse(inp).netloc
    if netloc in ("localhost:8080"):
        #  http://localhost:8080/pic/media%2FFEnXwX-UcAcJVQS.jpg%3Fname%3Dsmall
        #  http://localhost:8080/pic/ext_tw_video_thumb%2F1295395442272813056%2Fpu%2Fimg%2F5GKzCZ3-ifrhAeLN.jpg%3Asmall
        for patt, sub in (
            (r"(/pic/media%2F[^.]+\.[^%]+)%3F.*", "%3Fname%3Dorig"),
            (
                r"(/pic/ext_tw_video_thumb%2F.+%2Fpu%2Fimg%2F[^.]+\.[^%]+)%3A.*",
                "%3Aorig",
            ),
        ):
            if (
                new_url := re.sub(patt, lambda x: x.group(1) + sub, inp)
            ) and new_url != inp:
                return new_url


class NitterExtractor(Extractor):
    category = "nitter"
    pattern = BASE_PATTERN

    def items(self):
        if not (schema and tweets):
            return
        try:
            #  nitter1
            session = HTMLSession()
            base_url = parse.urlunparse(list(parse.urlparse(self.url)[:2]) + [""] * 4)
            for item in get_tweets(
                url=self.url, pages=1, log=self.log, session=session
            ):
                if val := item.get("tweet", None):
                    if isinstance(val, str):
                        self.log.error("error value type, %s", val)
                        continue
                    data = collections.defaultdict(list)
                    if val.username:
                        data["category_"].append(f"user:{val.username}")
                    if val.tweet_url:
                        data["url"].append(parse.urljoin(base_url, val.tweet_url))
                    if val.text:
                        data["description"].append(
                            (
                                f"{val.username}:{val.text}"
                                if val.username
                                else val.text
                            ).replace("\n", " ")
                        )
                    if val.entries and val.entries.hashtags:
                        for hashtag in val.entries.hashtags:
                            c_hashtag = hashtag.replace(":", " ")
                            if c_hashtag.startswith("#"):
                                c_hashtag = c_hashtag[1:]
                            data["hashtags"].append(c_hashtag)
                    if val.entries and val.entries.urls:
                        [data["url"].append(x) for x in val.entries.urls]
                    for url_part in [
                        *getattr(getattr(val, "entries", {}), "photos", []),
                        *getattr(getattr(val, "entries", {}), "videos", []),
                    ]:
                        url = parse.urljoin(base_url, url_part)
                        yield Message.Url, new_url if (
                            new_url := replace_url(url)
                        ) else url, data
                if val := item.get("next_url", None):
                    if isinstance(val, str):
                        yield Message.Queue, parse.urljoin(base_url, val), {}
                    else:
                        self.log.error("error value type, %s", val)
                        continue
        except Exception as err:
            raise err
