#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Server module."""
from urllib.parse import urljoin, urlparse
import logging
import re
import sys
import os

from bs4 import BeautifulSoup
try:
    from flask import (
        flash,
        Flask,
        redirect, url_for,
        render_template,
        request,
    )
    import peewee  # NOQA
except ImportError as e:
    print("Peewee and flask package required for server feature.")
    raise e

from .extractor.common import Extractor, Message
from .job import Job
from .exception import NoExtractorError
from . import models, extractor
from .models import (
    Post,
    PostMetadata,
    Gallery,
    Url,
)


app = Flask(__name__)


class CustomJob(Job):
    """Custom job."""

    def __init__(self, url):
        """Init method."""
        Job.__init__(self, url)
        self.gallery_data = {}
        self.images = []

    def handle_url(self, url, metadata):
        """Handle url."""
        self.images.append((url, metadata.copy()))

    def handle_directory(self, metadata):
        """handle directory."""
        self.gallery_data = metadata.copy()


class BlogLivedoorJpExtractor(Extractor):
    """Extract from blog.livedoor.jp."""

    regex = r'https?:\/\/blog.livedoor.jp\/.*'

    def __init__(self, match):
        """Init method."""
        Extractor.__init__(self)
        self.match = match

    def items(self):
        """Get items."""
        resp = self.session.get(self.match.group())
        soup = BeautifulSoup(resp.content, 'html.parser')
        hrefs = [
            x.attrs.get('href')
            for x in soup.select('a') if x.attrs.get('href').endswith('html')]
        valid_hrefs = []
        for href in hrefs:
            basename = os.path.splitext(os.path.basename(href))[0]
            if basename.isdigit():
                valid_hrefs.append(href)
        invalid_netlocs = ['parts.blog.livedoor.jp', 't.blog.livedoor.jp']
        for href in valid_hrefs:
            soup = BeautifulSoup(self.session.get(href).content, 'html.parser')
            for img_tag in soup.select('img'):
                img_src = img_tag.attrs.get('src')
                parsed_url = urlparse(img_src)
                if parsed_url.netloc in invalid_netlocs:
                    continue
                yield Message.Url, img_src, {}


class TheEyeExtractor(Extractor):
    """Extract from the-eye.eu."""

    regex = r'https?:\/\/the-eye\.eu\/public\/ripreddit\/.*'

    def __init__(self, match):
        """Init method."""
        Extractor.__init__(self)
        self.match = match

    def items(self):
        """get items."""
        resp = self.session.get(self.match.group())
        soup = BeautifulSoup(resp.content, 'html.parser')
        for tag in soup.select('a'):
            href = tag.attrs.get('href', None)
            invalid_starts_words = (
                'javascript:', '../', 'https://discord.gg',
                'https://www.reddit.com'
            )
            if href.startswith(invalid_starts_words):
                continue
            url = urljoin(self.match.group(), href)
            yield Message.Url, url, {}


def init_db():
    """Init db."""
    models.db.init('gallery_dl.db')
    models.db.create_tables([
        Gallery,
        Post,
        PostMetadata,
        Url,
    ], safe=True)


def get_or_create_posts(url_input, no_cache=False):
    """Get or create gallery."""
    url_input_m, _ = Url.get_or_create(url_input)
    gallery_m, _ = Gallery.get_or_create(url=url_input_m)
    posts_q = Post.select().where(Post.gallery == gallery_m)
    if posts_q.exists() and not no_cache:
        for entry in posts_q:
            yield entry, False
    job = CustomJob(url_input_m.value)
    job.run()
    if job.gallery_data:
        gallery_m.metadata.update(job.gallery_data)
        gallery_m.save()
    for idx, item in enumerate(job.images):
        img_url , img_metadata = item
        post_url_m, _ = Url.get_or_create(img_url)
        post_m, _ = Post.get_or_create(gallery=gallery_m, url=post_url_m)
        post_metadata_m, is_created = PostMetadata.get_or_create(post=post_m)
        if img_metadata:
            post_metadata_m.metadata.update(img_metadata)
            post_metadata_m.save()
        logging.debug('#{} idx image'.format(idx))
        yield post_metadata_m, is_created


@app.route('/')
def index():
    """Get index page."""
    url_input = request.args.get('url', None)
    if url_input is None:
        return render_template('index.html')
    url_input_m, _ = Url.get_or_create(value=url_input)
    gallery_m, _ = Gallery.get_or_create(url=url_input_m)
    return redirect(url_for('gallery', gallery_id=gallery_m.id))


def get_post(job, gallery_m):
    """Get post from job and gallery_model."""
    for idx, item in enumerate(job.images):
        img_url , img_metadata = item
        post_url_m, _ = Url.get_or_create(value=img_url)
        post_m, _ = Post.get_or_create(gallery=gallery_m, url=post_url_m)
        post_metadata_m, _ = PostMetadata.get_or_create(post=post_m)
        default_img_metadata = {'subcategory': '', 'category': ''}
        if img_metadata and img_metadata != default_img_metadata:
            try:
                post_metadata_m.metadata.update(img_metadata)
            except AttributeError:
                post_metadata_m.metadata = img_metadata
            post_metadata_m.save()
        yield post_m


@app.route('/g/', defaults={'page': 1, "gallery_id": None})
@app.route('/g/page/<int:page>', defaults={'gallery_id': None})
@app.route('/g/<int:gallery_id>', defaults={'page': 1})
@app.route('/g/<int:gallery_id>/page/<int:page>')
def gallery(gallery_id=None, page=1):
    """Get gallery."""
    no_cache = int(request.args.get('no-cache', 0)) == 1
    item_per_page = 36
    gallery_m = models.Gallery.get(id=gallery_id)
    posts_q = \
        Post.select() \
        .where(models.Post.gallery == gallery_m).paginate(page, item_per_page)
    entries = [x for x in posts_q if not x.is_video()]
    video_entries = [x for x in posts_q if x.is_video()]
    if posts_q.exists() and not no_cache:
        return render_template(
            'gallery.html', entries=entries, video_entries=video_entries,
            url_input=gallery_m.url.value)
    try:
        add_extr_cache_entry = [
            (re.compile(TheEyeExtractor.regex), TheEyeExtractor),
            (
                re.compile(BlogLivedoorJpExtractor.regex),
                BlogLivedoorJpExtractor
            ),
        ]
        extractor._cache.extend(add_extr_cache_entry)
        job = CustomJob(gallery_m.url.value)
        job.run()
        try:
            gallery_m.metadata.update(job.gallery_data)
        except AttributeError:
            gallery_m.metadata = job.gallery_data
        gallery_m.save()
        entries = list(get_post(job=job, gallery_m=gallery_m))[:item_per_page]
        return render_template(
            'gallery.html', entries=entries, url_input=gallery_m.url.value)
    except NoExtractorError:
        flash(
            'No Extractor found for {}.'.format(gallery_m.url.value), 'error')
        return redirect(url_for('index'))


@app.route('/p')
def gallery_post():
    """Get gallery post."""
    no_post_msg = 'No post found with that url.'
    url_input = request.args.get('u', None)
    post_url_m, is_created = models.get_or_create(url=url_input)
    if is_created:
        flash(no_post_msg, 'error')
        return redirect(url_for('index'))
    post_q = models.Post.select().where(models.Post.url == post_url_m)
    if not post_q.exists():
        flash(no_post_msg, 'error')
        return redirect(url_for('index'))
    return render_template('post.html', entries=post_q)


def main():
    """Get main function."""
    init_db()

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    log_fmt = '%(asctime)s-%(name)s-%(levelname)s-%(message)s'
    formatter = logging.Formatter(log_fmt)
    ch.setFormatter(formatter)
    root.addHandler(ch)
    app_run_kwargs = {'debug': True}
    app.run(**app_run_kwargs)


if __name__ == '__main__':
    main()
