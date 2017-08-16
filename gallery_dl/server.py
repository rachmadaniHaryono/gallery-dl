#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Server module."""
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

from .job import Job
from .exception import NoExtractorError
from . import models
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


def init_db():
    """Init db."""
    models.db.init('gallery_dl.db')
    models.db.create_tables([
        Gallery,
        Post,
        PostMetadata,
        Url,
    ], safe=True)


def get_or_create_posts(url_input):
    """Get or create gallery."""
    url_input_m, _ = Url.get_or_create(url_input)
    gallery_m, _ = Gallery.get_or_create(url=url_input_m)
    posts_q = Post.select().where(Post.gallery == gallery_m)
    if posts_q.exists():
        for entry in posts_q:
            yield entry, False
    job = CustomJob(url_input_m.value)
    job.run()
    gallery_m.metadata.update(job.gallery_data)
    gallery_m.save()
    for img_url , img_metadata in job.images:
        post_url_m, _ = Url.get_or_create(img_url)
        post_m, _ = Post.get_or_create(gallery=gallery_m, url=post_url_m)
        post_metadata_m, is_created = PostMetadata.get_or_create(post=post_m)
        post_metadata_m.metadata.update(img_metadata)
        post_metadata_m.save()
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
    for img_url , img_metadata in job.images:
        post_url_m, _ = Url.get_or_create(value=img_url)
        post_m, _ = Post.get_or_create(gallery=gallery_m, url=post_url_m)
        post_metadata_m, _ = PostMetadata.get_or_create(post=post_m)
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
    gallery_m = models.Gallery.get(id=gallery_id)
    posts_q = Post.select().where(models.Post.gallery == gallery_m)
    if posts_q.exists():
        return render_template(
            'gallery.html', entries=posts_q, url_input=gallery_m.url.value)
    try:
        job = CustomJob(gallery_m.url.value)
        job.run()
        try:
            gallery_m.metadata.update(job.gallery_data)
        except AttributeError:
            gallery_m.metadata = job.gallery_data
        gallery_m.save()
        entries = get_post(job=job, gallery_m=gallery_m)
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
    app_run_kwargs = {'debug': True}
    app.run(**app_run_kwargs)


if __name__ == '__main__':
    main()
