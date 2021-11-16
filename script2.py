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
import tqdm

from gallery_dl import config
from gallery_dl.exception import NoExtractorError
from gallery_dl.job import DataJob

UrlSetType = T.Set[str]
UrlDictType = collections.defaultdict[str, T.Set[str]]
DataJobListType = T.List[DataJob]
HandleJobResultType = T.TypedDict(
    "HandleJobResultType",
    {"url_dict": UrlDictType, "url_set": UrlSetType, "job_list": DataJobListType},
)


class BaseHandler:
    extractors: T.Sequence[str]

    @staticmethod
    def handle_job(
        job: DataJob, url_dict: UrlDictType, url_set: UrlSetType
    ) -> HandleJobResultType:
        job_list: DataJobListType = []
        key_dict = {
            "category_": "category:",
            "thread": "thread:",
            "person": "person:",
            "title": "title:",
            "label": "label:",
            "series": "series:",
            "person": "person:",
        }
        item: T.List[T.Any]
        for item in filter(lambda x: x[0] == 3, job.data):
            for key, namespace in key_dict.items():
                for subtag in item[2].get(key, []):
                    url_dict[item[1]].add(namespace + subtag)
            if item[1] not in url_dict:
                url_dict[item[1]] = set()
        for item in filter(lambda x: x[0] == 6 and x[1] not in url_set, job.data):
            try:
                job_list.append(DataJob(item[1]))
            except NoExtractorError:
                logging.error("no extractor, url: " + item[1])
            url_set.add(item[1])
        return HandleJobResultType(
            url_dict=url_dict, url_set=url_set, job_list=job_list
        )


class TwitterHandler(BaseHandler):
    extractors = (
        "TwitterMediaExtractor",
        "TwitterSearchExtractor",
        "TwitterTimelineExtractor",
        "TwitterTweetExtractor",
    )

    @staticmethod
    def handle_job(job, url_dict, url_set):
        job_list = []

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
                    tags.add(f"category:mention:nick:{mention_subtag}")
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

        for item in filter(lambda x: x[0] == 6 and x[1] not in url_set, job.data):
            try:
                job_list.append(DataJob(item[1]))
            except NoExtractorError:
                logging.error("no extractor, url: " + item[1])
            url_set.add(item[1])
        return dict(url_dict=url_dict, url_set=url_set, job_list=job_list)


class HentaicosplaysGalleryHandler:
    extractors = ("HentaicosplaysGalleryExtractor",)

    @staticmethod
    def handle_job(job, url_dict, url_set):
        job_list = []
        for item in filter(lambda x: x[0] == 3, job.data):
            subtag = item[2].get("title", None)
            if subtag:
                url_dict[item[1]].add("thread:" + subtag)
            if item[1] not in url_dict:
                url_dict[item[1]] = set()
        for item in filter(lambda x: x[0] == 6 and x[1] not in url_set, job.data):
            try:
                job_list.append(DataJob(item[1]))
            except NoExtractorError:
                logging.error("no extractor, url: " + item[1])
            url_set.add(item[1])
        return dict(url_dict=url_dict, url_set=url_set, job_list=job_list)


class ReactorHandler:
    extractors = ("ReactorTagExtractor", "ReactorExtractor")

    @staticmethod
    def handle_job(job, url_dict, url_set):
        job_list = []
        for item in filter(lambda x: x[0] == 3, job.data):
            for tag in item[2].get("tags", []):
                if tag:
                    url_dict[item[1]].add(tag.replace(":", " "))
            if item[1] not in url_dict:
                url_dict[item[1]] = set()
        for item in filter(lambda x: x[0] == 6 and x[1] not in url_set, job.data):
            try:
                job_list.append(DataJob(item[1]))
            except NoExtractorError:
                logging.error("no extractor, url: " + item[1])
            url_set.add(item[1])
        return dict(url_dict=url_dict, url_set=url_set, job_list=job_list)


class SankakuHandler:
    extractors = ("SankakuExtractor", "SankakuPostExtractor")

    @staticmethod
    def handle_job(job, url_dict, url_set):
        job_list = []
        for item in filter(lambda x: x[0] == 3, job.data):
            for tag in item[2].get("tag_string", "").split():
                if tag:
                    url_dict[item[1]].add(tag.replace(":", " ").replace("_", " "))
            if item[1] not in url_dict:
                url_dict[item[1]] = set()
        for item in filter(lambda x: x[0] == 6 and x[1] not in url_set, job.data):
            try:
                job_list.append(DataJob(item[1]))
            except NoExtractorError:
                logging.error("no extractor, url: " + item[1])
            url_set.add(item[1])
        return dict(url_dict=url_dict, url_set=url_set, job_list=job_list)


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
    while tqdm.tqdm(not jq.empty()):
        job = jq.get()
        job_url = job.extractor.url
        tqdm.tqdm.write("qsize:{}:url:{}".format(jq.qsize, job_url))
        job.run()
        if any(x[0] not in [2, 3, 6] for x in job.data):
            tqdm.tqdm.write(
                str({x[0] for x in job.data if x[0] not in [2, 3, 6]}) + ":" + job_url
            )
        for handler in [
            HentaicosplaysGalleryHandler,
            ReactorHandler,
            SankakuHandler,
            TwitterHandler,
        ]:
            if job.extractor.__class__.__name__ in handler.extractors:
                handle_func = handler.handle_job
                break
        else:
            handle_func = BaseHandler.handle_job
        res = handle_func(job, url_dict, url_set)
        for key, val in res.get("url_dict", {}).items():
            if not key:
                logging.debug("No key" + str(dict(key=key, tags=val)))
                continue
            url_dict[key].update(val)
        for item in res.get("url_set", set()):
            url_set.add(item)
        for item in res.get("job_list", []):
            jq.put(item)

    err_list = []
    for item in tqdm.tqdm(sorted(url_dict.items())):
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
            err_list.append((err, url, tags))
    [logging.error("{}:url:{}:tags:{}".format(*x)) for x in err_list]
