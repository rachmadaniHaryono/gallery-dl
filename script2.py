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

from gallery_dl import config
from gallery_dl.exception import NoExtractorError
from gallery_dl.job import DataJob

UrlSetType = T.Set[str]
UrlDictType = collections.defaultdict[str, T.Set[str]]
DataJobListType = T.List[DataJob]
ErrorItemType = T.TypedDict(
    "ErrorItemType",
    {
        "err": T.Union[NoExtractorError, hydrus.MissingParameter],
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


def create_tag(subtag: str, namespace: T.Optional[str] = None) -> str:
    if namespace:
        return namespace + subtag
    c_subtag = subtag.replace(":", " ")
    return c_subtag[1:] if c_subtag.startswith("#") else c_subtag


class BaseHandler:
    """base handler.

    url_set is used to avoid duplicate url when creating new job.
    """
    extractors: T.Sequence[str]

    @staticmethod
    def handle_job(job: DataJob, url_dict: UrlDictType) -> HandleJobResultType:
        """handle job data.

        Args:
            job: data job
            url_dict: url and tags
            url_set: unique urls

        """
        key_dict = {
            "description": "description:",
            "category_": "category:",
            "label": "label:",
            "person": "person:",
            "series": "series:",
            "thread": "thread:",
            "title": "title:",
            "url": "url:",
            "hashtags": "",
        }
        item: T.List[T.Any]
        for item in filter(lambda x: x[0] == 3, job.data):
            for key, namespace in key_dict.items():
                subitem: T.Union[str, T.List[str]] = item[2].get(key, [])
                if isinstance(subitem, str):
                    url_dict[item[1]].add(create_tag(subitem, namespace))
                else:
                    for subtag in subitem:
                        url_dict[item[1]].add(create_tag(subtag, namespace))
            if item[1] not in url_dict:
                url_dict[item[1]] = set()
        return HandleJobResultType(url_dict=url_dict)

    @staticmethod
    def iter_queue_urls(job: DataJob, url_set: T.Optional[UrlSetType] = None):
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


class TwitterHandler(BaseHandler):
    extractors = (
        "TwitterMediaExtractor",
        "TwitterSearchExtractor",
        "TwitterTimelineExtractor",
        "TwitterTweetExtractor",
    )

    @staticmethod
    def handle_job(job, url_dict):
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


class HentaicosplaysGalleryHandler(BaseHandler):
    extractors = ("HentaicosplaysGalleryExtractor",)

    @staticmethod
    def handle_job(job, url_dict):
        for item in filter(lambda x: x[0] == 3, job.data):
            subtag = item[2].get("title", None)
            if subtag:
                url_dict[item[1]].add("thread:" + subtag)
            if item[1] not in url_dict:
                url_dict[item[1]] = set()
        return dict(url_dict=url_dict)


class RedditHandler(BaseHandler):
    extractors = ("RedditSubmissionExtractor",)

    @staticmethod
    def handle_job(job: DataJob, url_dict: UrlDictType) -> HandleJobResultType:
        for item in filter(lambda x: x[0] == 3, job.data):
            if item[1] not in url_dict:
                url_dict[item[1]] = set()
            for key, tag_fmt in (
                ("author", "uploader:{subtag}"),
                ("link_flair_text", "category:{subtag}"),
                ("permalink", "url:https://www.reddit.com{subtag}"),
                ("subreddit", "category:subreddit:{subtag}"),
                ("title", "description:{subtag}"),
            ):
                if subtag := item[2].get(key, None):
                    url_dict[item[1]].add(tag_fmt.format(subtag=subtag))

        return HandleJobResultType(url_dict=url_dict)


class ReactorHandler(BaseHandler):
    extractors = ("ReactorTagExtractor", "ReactorExtractor")

    @staticmethod
    def handle_job(job, url_dict):
        for item in filter(lambda x: x[0] == 3, job.data):
            for tag in item[2].get("tags", []):
                if tag:
                    url_dict[item[1]].add(tag.replace(":", " "))
            if item[1] not in url_dict:
                url_dict[item[1]] = set()
        return HandleJobResultType(url_dict=url_dict)


class SankakuHandler(BaseHandler):
    extractors = ("SankakuExtractor", "SankakuPostExtractor")

    @staticmethod
    def handle_job(job, url_dict):
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
                        url_dict[item[1]].add("description:{key}{c_val}")
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
    for url in {x for x in urls if x}:
        try:
            jq.put(DataJob(url))
        except NoExtractorError as err:
            logging.error(f"url: {url}")
            raise err
    url_dict: UrlDictType = collections.defaultdict(set)
    url_set = set(urls)
    err_list: T.List[ErrorItemType] = []
    while tqdm.tqdm(not jq.empty()):
        job = jq.get()
        job_url = job.extractor.url
        tqdm.tqdm.write(f"qsize:{jq.qsize()}:len_url:{len(url_dict)}:url:{job_url}")
        job.file = open(os.devnull, "w")
        job.run()
        dict_to_print = collections.defaultdict(list)
        for item in job.data:
            dict_to_print[item[0]].append(list(item[1:]))
        for k, v in dict_to_print.items():
            tqdm.tqdm.write("key:" + str(k) + "\n" + yaml.dump(v, allow_unicode=True))
        if any(x[0] not in [2, 3, 6] for x in job.data):
            tqdm.tqdm.write(
                str({x[0] for x in job.data if x[0] not in [2, 3, 6]}) + ":" + job_url
            )
        for handler in [
            HentaicosplaysGalleryHandler,
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
        for res in [cls.handle_job(job, url_dict), cls.iter_queue_urls(job, url_set)]:
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

    for item in tqdm.tqdm(natsort.natsorted(url_dict.items())):
        url, tags = item
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
            (":" + str(err["err"]) if err["err"] else ""),
            "url",
            err["url"],
        ]
        for key in ["target_url", "tags"]:
            if val := err.get(key, None):
                msg_parts.extend([" " + key, str(val)])
        logging.error(":".join(msg_parts))
