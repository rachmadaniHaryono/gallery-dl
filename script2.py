#!/usr/bin/env python
# -*- coding: utf-8 -*-
import collections
import logging
import os
import queue

import hydrus
import tqdm

from gallery_dl import config
from gallery_dl.exception import NoExtractorError
from gallery_dl.job import DataJob


class TwitterHandler:
    extractors = (
        "TwitterMediaExtractor",
        "TwitterSearchExtractor",
        "TwitterTimelineExtractor",
        "TwitterTweetExtractor",
    )

    @staticmethod
    def handle_job(job, url_dict, url_set):
        job_list = []
        for item in filter(lambda x: x[0] == 3, job.data):
            # main url
            tags = set()
            tags.add("category:author:nick:" + item[2]["author"]["nick"])
            tags.add("category:author:name:" + item[2]["author"]["name"])
            subtag = item[2]["user"]["name"]
            if subtag and ("category:author:name:" + subtag) not in tags:
                tags.add("category:user:name:" + subtag)
            subtag = item[2]["user"]["nick"]
            if subtag and ("category:author:nick:" + subtag) not in tags:
                tags.add("category:user:nick:" + subtag)
            tags.add("description:" + item[2]["content"])
            for tag in item[2].get("hashtags", []):
                tags.add(tag.replace(":", " "))
            for mention in item[2].get("mentions", []):
                subtag = mention.get("nick", None)
                if subtag and ("category:author:nick:" + subtag) not in tags:
                    tags.add("category:mention:nick:" + subtag)
                subtag = mention.get("name", None)
                if subtag and ("category:author:name:" + subtag) not in tags:
                    tags.add("category:mention:name:" + subtag)
            if item[1]:
                url_dict[item[1]].update(tags)
            # profile_banner and profile_image in author section
            tags = set()
            author = item[2]["author"]
            tags.add("category:author:nick:" + author["nick"])
            tags.add("category:author:name:" + author["name"])
            tags.add("description:" + author["description"])
            for url in [
                author["profile_banner"],
                author["profile_banner"],
            ]:
                if not url:
                    continue
                url_dict[url].update(tags)
            # profile_banner and profile_image in author section
            user = item[2]["user"]
            user_name = user["name"]
            user_nick = user["nick"]
            for url in [
                user["profile_banner"],
                user["profile_banner"],
            ]:
                if not url:
                    continue
                url_dict[url].add("description:" + user["description"])
                if (
                    user_name
                    and ("category:author:name:" + subtag) not in url_dict[url]
                ):
                    url_dict[url].add("category:user:name:" + user_name)
                if (
                    user_nick
                    and ("category:author:nick:" + subtag) not in url_dict[url]
                ):
                    url_dict[url].add("category:user:nick:" + user_nick)

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


def handle_job(job, url_dict, url_set):
    job_list = []
    key_dict = {
        "category_": "category:",
        "thread": "thread:",
        "person": "person:",
        "title": "title:",
        "label": "label:",
        "series": "series:",
        "person": "person:",
    }
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
    return dict(url_dict=url_dict, url_set=url_set, job_list=job_list)


def send_url(urls):
    cl = hydrus.Client(os.getenv("HYDRUS_ACCESS_KEY"))
    jq = queue.Queue()  # job queue
    config.load()
    for url in set(urls):
        try:
            jq.put(DataJob(url))
        except NoExtractorError as err:
            logging.error(f"url: {url}")
            raise err
    url_dict = collections.defaultdict(set)
    url_set = set(urls)
    while not jq.empty():
        job = jq.get()
        job.run()
        if any(x[0] not in [2, 3, 6] for x in job.data):
            print(
                str(set(x[0] for x in job.data if x[0] not in [2, 3, 6]))
                + ":"
                + job.extractor.url
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
            handle_func = handle_job
        res = handle_func(job, url_dict, url_set)
        for key, val in res.get("url_dict", {}).items():
            if not key:
                logging.debug("No key" + str(dict(key=key, tags=tags)))
                continue
            url_dict[key].update(val)
        for item in res.get("url_set", set()):
            url_set.add(item)
        for item in res.get("job_list", []):
            jq.put(item)

    for item in tqdm.tqdm(sorted(url_dict.items())):
        url, tags = item
        tqdm.tqdm.write(str(item))
        kwargs = {"url": url}
        if tags:
            kwargs["service_names_to_additional_tags"] = {"my tags": list(tags)}
        try:
            cl.add_url(**kwargs)
        except hydrus.MissingParameter as err:
            logging.error("MissingParameter:{}".format(dict(url=url, tags=tags)))
