#!/usr/bin/env python
# -*- coding: utf-8 -*-
import collections
import html
import logging
import os
import queue
import typing as T
from os import path
from urllib import parse

import hydrus
import natsort
import tqdm
import yaml

from gallery_dl import config, output
from gallery_dl.exception import NoExtractorError
from gallery_dl.extractor.common import get_soup
from gallery_dl.job import DataJob

UrlSetType = T.Set[str]
UrlDictType = collections.defaultdict[str, T.Set[str]]
DataJobListType = T.List[DataJob]
ErrorItemType = T.TypedDict(
    "ErrorItemType",
    {
        "err": T.Union[
            NoExtractorError, hydrus.MissingParameter, ValueError, Exception
        ],
        "url": str,
        "tags": T.Any,
        "target_url": T.Optional[str],
    },
)
HandleJobResultType = T.TypedDict(
    "HandleJobResultType",
    {
        "url_dict": UrlDictType,
        "url_set": UrlSetType,
        "job_list": DataJobListType,
        "error_list": T.List[ErrorItemType],
    },
    total=False,
)


def create_tag(subtag: T.Union[str, int], tag_fmt: T.Optional[str] = None) -> str:
    if tag_fmt:
        return tag_fmt.format(subtag=subtag)
    c_subtag = str(subtag).replace(":", " ")
    return c_subtag[1:] if c_subtag.startswith("#") else c_subtag


class BaseHandler:
    """base handler.

    url_set is used to avoid duplicate url when creating new job.
    """
    extractors: T.Sequence[str]

    key_dict = {
        "description": "description:{subtag}",
        "category_": "category:{subtag}",
        "label": "label:{subtag}",
        "person": "person:{subtag}",
        "series": "series:{subtag}",
        "thread": "thread:{subtag}",
        "title": "title:{subtag}",
        "url": "url:{subtag}",
        "hashtags": None,
    }

    @classmethod
    def handle_job(cls, job: DataJob, url_dict: UrlDictType) -> HandleJobResultType:
        """handle job data.

        Args:
            job: data job
            url_dict: url and tags
            url_set: unique urls

        """
        item: T.List[T.Any]
        for item in filter(lambda x: x[0] == 3, job.data):
            for key, tag_fmt in cls.key_dict.items():
                subitem: T.Union[str, T.List[str]] = item[2].get(key, [])
                if not subitem:
                    continue
                if isinstance(subitem, (str, int)):
                    url_dict[item[1]].add(create_tag(subitem, tag_fmt))
                else:
                    for subtag in subitem:
                        url_dict[item[1]].add(create_tag(subtag, tag_fmt))
            if item[1] not in url_dict:
                url_dict[item[1]] = set()
        return HandleJobResultType(url_dict=url_dict)

    @staticmethod
    def iter_queue_urls(
        job: DataJob, url_set: T.Optional[UrlSetType] = None
    ) -> HandleJobResultType:
        if url_set is None:
            url_set = set()
        error_list: T.List[ErrorItemType] = []
        job_list = []
        for item in filter(lambda x: x[0] == 6 and x[1] not in url_set, job.data):
            try:
                job_list.append(DataJob(item[1]))
            except NoExtractorError as err:
                error_list.append(
                    ErrorItemType(
                        err=err, url=job.extractor.url, tags=None, target_url=item[1]
                    )
                )
            url_set.add(item[1])
        return HandleJobResultType(
            url_set=url_set, job_list=job_list, error_list=error_list
        )


class ExhentaiHandler(BaseHandler):
    extractors = ("ExhentaiGalleryExtractor",)
    key_dict = {
        "title": "title:{subtag}",
        "title_jpn": "description:title_ja:{subtag}",
        "eh_category": "category:{subtag}",
        "lang": "category:lang:{subtag}",
        "filename": "filename:{subtag}",
        "num": "page:{subtag}",
    }

    @classmethod
    def handle_job(cls, job: DataJob, url_dict: UrlDictType) -> HandleJobResultType:
        res = super(cls, cls).handle_job(job=job, url_dict=url_dict)
        res.setdefault("url_dict", UrlDictType())
        for item in filter(lambda x: x[0] == 3 and x[2], job.data):
            for tag in item[2].get("tags", []):
                c_tag = (
                    "series:" + tag.split("parody:", 1)[1]
                    if tag.startswith("parody:")
                    else tag
                )
                res["url_dict"][item[1]].add(f"category:{c_tag}")
        return res


class _4chanHandler(BaseHandler):

    extractors = ("_4chanThreadExtractor",)

    @classmethod
    def handle_job(cls, job: DataJob, url_dict: UrlDictType) -> HandleJobResultType:
        cls.key_dict["title"] = "thread:{subtag}"
        cls.key_dict["filename"] = "filename:{subtag}"
        del cls.key_dict["thread"]
        res = super(cls, cls).handle_job(job=job, url_dict=url_dict)
        res.setdefault("url_dict", UrlDictType())
        for item in filter(lambda x: x[0] == 3 and x[2], job.data):
            if (subtag := item[2].get("com")) and (
                soup_text := get_soup(subtag)
                .get_text(separator="\n")
                .replace("\n", " ")
            ):
                res["url_dict"][item[1]].add(f"description:{soup_text}")
        return res


class InstagramHandler(BaseHandler):
    extractors = (
        "InstagramChannelExtractor",
        "InstagramHighlightsExtractor",
        "InstagramPostExtractor",
        "InstagramPostsExtractor",
        "InstagramReelsExtractor",
        "InstagramStoriesExtractor",
        "InstagramTaggedExtractor",
        "InstagramUserExtractor",
    )
    key_dict = {
        "username": "category:user:{subtag}",
        "fullname": "category:fullname:{subtag}",
    }

    @classmethod
    def handle_job(cls, job: DataJob, url_dict: UrlDictType) -> HandleJobResultType:
        res = super(InstagramHandler, InstagramHandler).handle_job(
            job=job, url_dict=url_dict
        )
        if "url_dict" not in res:
            res["url_dict"] = UrlDictType()
        for item in filter(lambda x: x[0] == 3 and x[2], job.data):
            tags = set()
            if description := item[2].get("description"):
                if "\n" in description:
                    description = description.replace("\n", " ")
                tags.add(
                    f"description:{username}:{description}"
                    if (username := item[2].get("username"))
                    else f"description:{description}"
                )
            for subtag in item[2].get("tags", []):
                if subtag.startswith("#"):
                    subtag = subtag[1:]
                tags.add(f"ig:{subtag}")
            # ignore type because unknown "Could not access item in TypedDict" error
            if tags:
                res["url_dict"][item[1]].update(tags)  # type:ignore
            # final section, send display_url with tags from the item
            if url := item[2].get("display_url"):
                [
                    res["url_dict"][url].add(x)  # type:ignore
                    for x in res["url_dict"][item[1]]  # type: ignore
                ]
        return res


class ImgurHandler(BaseHandler):
    extractors = ("ImgurAlbumExtractor" "ImgurImageExtractor",)
    key_dict = {
        "title": "description:title:{subtag}",
        "description": "description:{subtag}",
        "name": "description:name:{subtag}",
    }


class TwitterHandler(BaseHandler):
    extractors = (
        "TwitterMediaExtractor",
        "TwitterSearchExtractor",
        "TwitterTimelineExtractor",
        "TwitterTweetExtractor",
    )

    @classmethod
    def handle_job(cls, job, url_dict):
        def get_subtag_from_dict(inp_dict: T.Dict[str, str]) -> str:
            return (
                inp_dict["name"]
                if inp_dict["nick"] == inp_dict["name"]
                else "{} ({})".format(inp_dict["name"], inp_dict["nick"])
            )

        for item in filter(lambda x: x[0] == 3, job.data):
            # main url
            author = item[2]["author"]
            user = item[2]["user"]
            tags = set()
            author_subtag = get_subtag_from_dict(author)
            tags.add(f"category:author:{author_subtag}")
            if (user_subtag := get_subtag_from_dict(user)) != author_subtag:
                tags.add(f"category:user:{user_subtag}")
            tags.add(
                "description:{}:{}".format(
                    author["name"], html.unescape(item[2]["content"].replace("\n", " "))
                )
            )
            for tag in item[2].get("hashtags", []):
                tags.add(tag.replace(":", " "))
            for mention in item[2].get("mentions", []):
                if (mention_subtag := get_subtag_from_dict(mention)) != author_subtag:
                    tags.add(f"category:mention:{mention_subtag}")
            if item[1]:
                url_dict[item[1]].update(tags)
            for key, subtag in [(author, author_subtag), (user, user_subtag)]:
                tags = set()
                tags.add(f"description:{key['description']}")
                tags.add(f"category:{subtag}")
                if url := key.get("url", None):
                    tags.add(f"url:{url}")
                for p_url in [
                    author["profile_banner"],
                    author["profile_image"],
                ]:
                    if p_url:
                        url_dict[p_url].update(tags)
        return dict(url_dict=url_dict)


class BakufuHandler(BaseHandler):
    extractors = ("BakufuGalleryExtractor",)
    key_dict = {
        "category_": "category:{subtag}",
        "title": "thread:{subtag}",
    }


class HentaicosplaysGalleryHandler(BaseHandler):
    extractors = ("HentaicosplaysGalleryExtractor",)
    key_dict = {
        "title": "thread:{subtag}",
    }


class RedditHandler(BaseHandler):
    extractors = ("RedditSubmissionExtractor",)


    key_dict = {
        "author": "uploader:{subtag}",
        "link_flair_text": "category:{subtag}",
        "permalink": "url:https://www.reddit.com{subtag}",
        "subreddit": "category:subreddit:{subtag}",
        "title": "description:{subtag}",
    }

    @staticmethod
    def iter_queue_urls(
        job: DataJob, url_set: T.Optional[UrlSetType] = None
    ) -> HandleJobResultType:
        res = super(RedditHandler, RedditHandler).iter_queue_urls(
            job=job, url_set=url_set
        )
        job_list = res.get("job_list", [])
        new_job_list = []
        res.setdefault("url_dict", collections.defaultdict(set))
        for job in job_list:
            try:
                extractor_name = job.extractor.__class__.__name__
                if extractor_name in (
                    "DanbooruPostExtractor",
                    "PixivWorkExtractor",
                ):
                    res["url_dict"].setdefault(job.extractor.url, set())
                elif extractor_name in (
                    "TwitterTimelineExtractor",
                    "InstagramUserExtractor",
                ):
                    logging.debug("skip url, %s", job.extractor.url)
                    pass
                else:
                    new_job_list.append(job)
            except Exception as err:
                logging.error(str(err))
                new_job_list.append(job)
        res["job_list"] = new_job_list
        return res


class ReactorHandler(BaseHandler):
    extractors = ("ReactorTagExtractor", "ReactorExtractor")

    @classmethod
    def handle_job(cls, job, url_dict):
        for item in filter(lambda x: x[0] == 3, job.data):
            for tag in item[2].get("tags", []):
                if tag:
                    url_dict[item[1]].add(tag.replace(":", " "))
            if item[1] not in url_dict:
                url_dict[item[1]] = set()
        return HandleJobResultType(url_dict=url_dict)


class SankakuHandler(BaseHandler):
    extractors = ("SankakuExtractor", "SankakuPostExtractor")

    @classmethod
    def handle_job(cls, job, url_dict):
        for item in filter(lambda x: x[0] == 3, job.data):
            for tag in item[2].get("tag_string", "").split():
                if tag:
                    url_dict[item[1]].add(tag.replace(":", " ").replace("_", " "))
            if item[1] not in url_dict:
                url_dict[item[1]] = set()
        return HandleJobResultType(url_dict=url_dict)


class NhentaiHandler(BaseHandler):
    extractors = ("NhentaiGalleryExtractor",)

    @staticmethod
    def handle_job(job, url_dict):
        for item in filter(lambda x: x[0] == 3, job.data):
            if item[1] not in url_dict:
                url_dict[item[1]] = set()
            title = None
            for key in ("title", "title_en", "title_ja"):
                if c_val := item[2].get(key, None):
                    if title is None:
                        title = c_val
                        continue
                    if title == c_val:
                        continue
                    else:
                        url_dict[item[1]].add(f"description:{key}:{c_val}")
            if title:
                url_dict[item[1]].add(f"title:{title}")
            if val := item[2].get("num", None):
                url_dict[item[1]].add(f"page:{val}")
            for key, mark in (
                ("scanlator", "scanlator"),
                ("artist", "artist"),
                ("group", "group"),
                ("parody", "series"),
                ("characters", "character"),
                ("tags", ""),
                ("type", ""),
                ("language", "language"),
            ):
                val = item[2].get(key, None)
                if not val:
                    pass
                elif isinstance(val, list):
                    [
                        url_dict[item[1]].add(
                            ":".join(["category", mark, x] if mark else ["category", x])
                        )
                        for x in val
                    ]
                else:
                    url_dict[item[1]].add(
                        ":".join(["category", mark, val] if mark else ["category", val])
                    )
        return HandleJobResultType(url_dict=url_dict)


def send_url(urls: T.List[str]):
    cl = hydrus.Client(os.getenv("HYDRUS_ACCESS_KEY"))
    jq: "queue.Queue[DataJob]" = queue.Queue()
    config.load()
    # initialze logging and setup logging handler to stderr
    output.initialize_logging(logging.WARNING)
    # apply config options to stderr handler and create file handler
    output.configure_logging(logging.INFO)
    # create unsupported-file handler
    output.setup_logging_handler("unsupportedfile", fmt="{message}")
    err_list: T.List[ErrorItemType] = []
    for url in {x for x in urls if x}:
        try:
            jq.put(DataJob(url))
        except NoExtractorError as err:
            logging.error(f"url: {url}")
            err_list.append(ErrorItemType(err=err, url=url, tags=None, target_url=None))
    url_dict: UrlDictType = collections.defaultdict(set)
    url_set = set(urls)
    while tqdm.tqdm(not jq.empty()):
        job = jq.get()
        job_url = job.extractor.url
        try:
            tqdm.tqdm.write(f"qsize:{jq.qsize()}:len_url:{len(url_dict)}:url:{job_url}")
            with open(os.devnull, "w") as f:
                job.file = f
                job.run()
            dict_to_print = collections.defaultdict(list)
            for item in job.data:
                dict_to_print[item[0]].append(list(item[1:]))
            for k, v in dict_to_print.items():
                tqdm.tqdm.write(
                    "key:" + str(k) + "\n" + yaml.dump(v, allow_unicode=True)
                )
            if any(x[0] not in [2, 3, 6] for x in job.data):
                tqdm.tqdm.write(
                    str({x[0] for x in job.data if x[0] not in [2, 3, 6]})
                    + ":"
                    + job_url
                )
            for handler in [
                _4chanHandler,
                BakufuHandler,
                ExhentaiHandler,
                HentaicosplaysGalleryHandler,
                ImgurHandler,
                InstagramHandler,
                NhentaiHandler,
                ReactorHandler,
                RedditHandler,
                SankakuHandler,
                TwitterHandler,
            ]:
                if job.extractor.__class__.__name__ in handler.extractors:
                    cls = handler
                    break
            else:
                cls = BaseHandler
            for res in [
                cls.handle_job(job=job, url_dict=url_dict),
                cls.iter_queue_urls(job, url_set),
            ]:
                for key, val in res.get("url_dict", {}).items():
                    if not key:
                        logging.debug("No key" + str(dict(key=key, tags=val)))
                        continue
                    url_dict[key].update(val)
                for item in res.get("url_set", set()):
                    url_set.add(item)
                for item in res.get("job_list", []):
                    jq.put(item)
                for item in res.get("error_list", []):
                    err_list.append(item)
        except Exception as err:
            logging.exception(err)
            err_list.append(
                ErrorItemType(err=err, url=job_url, tags=None, target_url=None)
            )

    for item in tqdm.tqdm(natsort.natsorted(url_dict.items())):
        url, tags = item
        if url.startswith("ytdl:"):
            err_list.append(
                ErrorItemType(
                    err=ValueError("ytdl not supported"),
                    url=url,
                    tags=tags,
                    target_url=None,
                )
            )
            continue
        ext = path.splitext(parse.urlparse(url).path)[1].lower()
        tqdm.tqdm.write(str(item))
        kwargs = {"url": url}
        if tags:
            kwargs["service_names_to_additional_tags"] = {"my tags": list(tags)}
        if ext in (".gif", ".webm", ".mp4"):
            kwargs["page_name"] = "video"
        try:
            cl.add_url(**kwargs)
        except hydrus.MissingParameter as err:
            err_list.append(ErrorItemType(err=err, url=url, tags=tags, target_url=None))
    for err in err_list:
        msg_parts = [
            err["err"].__class__.__name__,
            (str(err["err"]) if err["err"] else ""),
            "url",
            err["url"],
        ]
        for key in ["target_url", "tags"]:
            if val := err.get(key, None):
                msg_parts.extend([" " + key, str(val)])
        logging.error(":".join(msg_parts))
