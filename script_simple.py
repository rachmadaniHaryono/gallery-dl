#!/usr/bin/env python
"""
pip install camelsplit schema
"""
import logging
import os
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Callable
from urllib.parse import urlparse

import click
import hydrus
import sh
import tqdm
import yaml
from camelsplit import camelsplit
from flask import jsonify, request
from pymongo import MongoClient

from gallery_dl import config, option
from gallery_dl.exception import NoExtractorError
from gallery_dl.extractor.message import Message
from gallery_dl.job import DataJob


def get_json():
    data = []
    parser = option.build_parser()
    args = parser.parse_args()
    args.urls = request.args.getlist('url')
    if not args.urls:
        return jsonify({'error': 'No url(s)'})
    args.list_data = True
    for url in args.urls:
        url_res = None
        error = None
        try:
            job = DataJob(url)
            job.run()
            url_res = job.data
        except NoExtractorError as err:
            error = err
        data_item = [url, url_res, {'error': str(error) if error else None}]
        data.append(data_item)
    return jsonify({'data': data, 'urls': args.urls})


@click.group()
def cli():
    """This is a script for application."""
    pass


def convert_instagram_tags(
        tags: List[str],
        tag_cache: Dict[str, str],
        tag_blacklist: List[str]
) -> Tuple[List[Any], Dict[str, str], List[str]]:
    res = []
    for tag in tags:
        if tag in tag_cache:
            res.append(tag_cache[tag])
        elif tag in tag_blacklist:
            res.append(tag)
        else:
            if tag.startswith('#'):
                res_tag = tag[1:]
            else:
                res_tag = tag
            res_tag = ' '.join(camelsplit(res_tag)).strip()
            if not res_tag:
                pass
            elif tag == res_tag:
                tag_blacklist.append(res_tag)
            else:
                tag_cache[tag] = res_tag
            res.append(res_tag)
    return res, tag_cache, tag_blacklist


def convert_instagram_data(
        data: List[Any], tag_cache: Optional[Dict[str, str]] = None,
        tag_blacklist: Optional[List[str]] = None):
    res = defaultdict(list)
    tag_cache = tag_cache or {}
    tag_blacklist = tag_blacklist or []
    for item in data:
        if item[0] in [Message.Directory, Message.Url]:
            data_dict = item[1] if item[0] == 2 else item[2]
            tags = [
                'description:{}'.format(data_dict['description']),
                'creator:{}'.format(data_dict['fullname']),
                'creator:{}'.format(data_dict['username']),
            ]
            res_tags, tag_cache, tag_blacklist = convert_instagram_tags(
                data_dict.get('tags', []), tag_cache, tag_blacklist)
            tags.extend(res_tags)
            res[data_dict['display_url']].extend(tags)
            if item[0] == 389:
                res[item[1]].extend(tags)
        else:
            print('unknown data\n{}'.format(item))
    for key, value in res.items():
        if key:
            res[key] = list(set(value))
    return res


def convert_tweet_data(data: List[Any]):
    res = defaultdict(list)
    for item in data:
        if item[0] in [2, 3, 7]:
            actor_tags = defaultdict(list)
            for key in ["author", 'user']:
                item_data = item[1] if item[0] == 2 else item[2]
                if key not in item_data:
                    continue
                actor = item_data[key]
                actor_tags[key].extend([
                    'creator:{}'.format(actor['name']),
                    'creator:{}'.format(actor['nick'])])
                res[actor['profile_banner']].extend(actor_tags[key])
                res[actor['profile_image']].extend(actor_tags[key])
            if item[0] in [3, 7]:
                if item[0] == 7:
                    urls = [
                        x for x in item[1]
                        if x.rsplit(':', 1)[1] in ['orig', 'large']]
                else:
                    urls = [item[1]]
                tags = actor_tags['author'] \
                    if actor_tags['author'] else actor_tags['user']
                tags.append('description:{}'.format(item[2]['content']))
                list(map(lambda x: res[x].extend(tags), urls))
        else:
            print('unknown data\n{}'.format(item))
    for key, value in res.items():
        if key:
            res[key] = list(set(value))
    return res


@cli.command()
@click.argument('urls', nargs=-1)
def send_url(urls):
    cl = hydrus.Client(
        '918efdc1d28ae710b46fc814ee818100a102786140ede877db94cedf3d733cc1')
    for url in tqdm.tqdm(urls):
        config.set((), 'cookies', '/home/q/Downloads/cookies.txt')
        tqdm.tqdm.write('url: {}'.format(url))
        j = DataJob(url)
        j.run()
        parsed_url = urlparse(url)
        if parsed_url.netloc in ['www.instagram.com', 'instagram.com']:
            hydrus_data = convert_instagram_data(j.data)
        elif parsed_url.netloc in ['twitter.com']:
            hydrus_data = convert_tweet_data(j.data)
        else:
            raise NotImplementedError
        for item in tqdm.tqdm(hydrus_data.items()):
            k, v = item
            res = cl.add_url(k, service_names_to_tags={'my tags': v})
            tqdm.tqdm.write(str(res))


@cli.command()
@click.option('--config-file')
def process_html(config_file):
    # load from clipboard
    logger = logging.getLogger('process_html')
    html = sh.copyq.clipboard(['text/html'])
    if not html:
        logger.info('No html found')
        return
    # load config
    with open(config_file) as f:
        config_data = yaml.safe_load(f)
    # save to html folder
    target_filename = os.path.join(
        config_data['html_folder'], '{}.html'.format(
            datetime.now().strftime("%Y%m%d-%H%M%S")))
    with open(target_filename, 'w') as f:
        f.write(str(html))
    # parse all link
    # parse all image
    # parse meta
    # only send image not in hydrus
    pass


def run_gallery_dl_data_job(
        url: str,
        hydrus_client = None,
        tag_func: Optional[Callable[[Dict[str, Any]], List[str]]] = None
) -> Tuple[Any, Any, Any]:
    """run gallery_dl data job.

    :param url: url to process.
    :param hydrus_client: instance of hydrus_client.
    :param tag_func: function to generate tag from gallery_dl item.
    :return: Tuple of job instance, hydrus data and db data.

    Example:

    >>> def func1(item):
    ...     "return a tag and some tags from gallery_dl item"
    ...     return ['tag1'] + item[2].get('tags', [])
    ...
    ... run_gallery_dl_data_job('http://example.com', func1)
    """
    job = DataJob(url)
    job.run()
    # may contain 2 or 3 item tuple or single string such as
    # >>> [x for x in j.data if not isinstance(x[0], int)]
    # [('JSONDecodeError', 'Expecting value: line 1 column 1 (char 0)')]
    hydrus_data = []
    db_data = []
    for item in tqdm.tqdm(job.data):
        if not isinstance(item[0], int):
            print(item)
        elif len(item) == 2:
            item[1]['gallery_dl_message'] = item[0]
            item[1]['gallery_dl_input_url'] = url
            db_data.append(item[1])
        elif len(item) == 3:
            item[2]['gallery_dl_message'] = item[0]
            item[2]['gallery_dl_url'] = item[1]
            item[2]['gallery_dl_input_url'] = url
            db_data.append(item[2])
            tags = []
            if tag_func:
                tags = tag_func(item)
            hydrus_data.append({'url': item[1], 'tags': tags})
        else:
            print(item)
    if db_data:
        client = MongoClient()
        db = client.gallery_dl
        db.posts.insert_many(db_data)
    else:
        print('empty db_data, job data:\n{}'.format(job.data))
    for data in tqdm.tqdm(hydrus_data):
        hydrus_client.add_url(data['url'], service_names_to_additional_tags={
            'my tags': data.get('tags', [])})
    return job, hydrus_data, db_data


def send_instagram_url(username: str, cookies_path: str):
    cl = hydrus.Client(
        '918efdc1d28ae710b46fc814ee818100a102786140ede877db94cedf3d733cc1')
    url = 'https://instagram.com/{}'.format(username)
    config.set((), 'cookies', cookies_path)

    def get_tags(item):
        tags = ['thread:{}'.format(username)]
        tags.extend(item[2].get('tags', []))
        description = item[2].get('description', None)
        if description:
            description = description.replace('\n', ' ')
            tags.append('description:'.format(description))
        return tags

    run_gallery_dl_data_job(url, cl, get_tags)


def send_reddit_url(subreddit: str):
    cl = hydrus.Client(
        '918efdc1d28ae710b46fc814ee818100a102786140ede877db94cedf3d733cc1')
    url = 'https://reddit.com/r/{}'.format(subreddit)

    def get_tags(item):
        tags = ['thread:{}'.format(subreddit)]
        tags.extend(item[2].get('tags', []))
        if item[2].get('description', None):
            tags.append(item[2]['description'].replace('\n', ' '))
        return tags

    run_gallery_dl_data_job(url, cl, get_tags)


def send_pornhub_photo_album(id_: Any):
    cl = hydrus.Client(
        '918efdc1d28ae710b46fc814ee818100a102786140ede877db94cedf3d733cc1')
    url = 'https://www.pornhub.com/album/{}'.format(id_)

    def get_tags(item):
        tags = []
        item_tags = item[2].get('gallery', {}).get('tags', [])
        if item_tags:
            tags.extend(['category:{}'.format(x) for x in item_tags])
        category = item[2].get('category', None)
        if category:
            tags.append('category:{}'.format(category))
        creator = item[2].get('user', None)
        if creator:
            tags.append('creator:{}'.format(creator))
        thread = item[2].get('gallery', {}).get('title', None)
        if thread:
            tags.append('thread:{}'.format(thread))
        return tags

    run_gallery_dl_data_job(url, cl, get_tags)


def send_twitter_url(url_part: str):
    cl = hydrus.Client(
        '918efdc1d28ae710b46fc814ee818100a102786140ede877db94cedf3d733cc1')
    url = 'https://twitter.com/{}'.format(url_part)
    extra_items = defaultdict(list)

    def get_tags(item):
        tags = ['thread:{}'.format(url_part)]
        hashtags = item[2].get('hashtags', [])
        for tag in hashtags:
            tags.append(' '.join(camelsplit(tag)))
        description = item[2].get('content', None)
        if description:
            tags.append('description:{}'.format(description.replace('\n', ' ')))

        def get_name_and_nick_tags(dict_input, key):
            res = []
            for subkey in ['name', 'nick']:
                sub_tag = dict_input.get(subkey, None)
                if sub_tag:
                    res.append('category:{}:{}:{}'.format(key, subkey, sub_tag))
            return res

        for key in ['author', 'user']:
            nn_tags = []
            nn_tags.extend(get_name_and_nick_tags(item[2].get(key, {}), key=key))
            if nn_tags:
                tags.extend(nn_tags)
            sub_description = item[2].get(key, {}).get('description', None)
            for subkey in ['profile_banner', "profile_image"]:
                pf_url = item[2].get(key, {}).get(subkey, None)
                sub_tags = nn_tags
                if sub_description:
                    sub_tags.append('description:{}'.format(sub_description.replace('\n', ' ')))
                if pf_url and sub_tags:
                    extra_items[pf_url].extend(sub_tags)
                elif pf_url and pf_url not in extra_items:
                    extra_items[pf_url] = []
        for mention in item[2].get('mentions', []):
            nn_tags = get_name_and_nick_tags(mention, 'mentions')
            if nn_tags:
                tags.extend(nn_tags)
        return tags

    run_gallery_dl_data_job(url, cl, get_tags)
    for key, value in tqdm.tqdm(extra_items.items()):
        cl.add_url(key, service_names_to_additional_tags={'my tags': value})


def send_url(url: str, tags: Optional[List[str]] = None):
    cl = hydrus.Client(
        '918efdc1d28ae710b46fc814ee818100a102786140ede877db94cedf3d733cc1')

    def get_tags(item):
        return tags

    if tags is None:
        run_gallery_dl_data_job(url, cl)
    else:
        run_gallery_dl_data_job(url, cl, get_tags)


if __name__ == '__main__':
    #  cli()
    pass
