#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json

from flask import Flask, render_template, request
import peewee

from .job import DataJob
from .exception import NoExtractorError
from . import models




app = Flask(__name__)


class CustomDataJob(DataJob):

    def get_data(self):
        """get data."""
        try:
            for msg in self.extractor:
                copy = [
                    part.copy() if hasattr(part, "copy") else part
                    for part in msg
                ]
                self.data.append(copy)
        except Exception as exc:
            self.data.append((exc.__class__.__name__, str(exc)))
        return self.data


def get_or_create_gallery(url_input):
    """get or create gallery."""
    models.db.init('gallery_dl.db')
    models.Gallery.create_table(True)
    entries = [
        x.to_dataset()
        for x in models.Gallery.select().where(models.Gallery.src_url == url_input)
    ]
    if entries:
        return entries
    job = CustomDataJob(url_input)
    entries = job.get_data()[2:]
    list(map(lambda x: models.Gallery.save_from_dataset(x, url_input), entries))
    return entries


@app.route('/')
def index():
    url_input = request.args.get('url', None)
    if url_input is None:
        return render_template('index.html')
    try:
        entries = get_or_create_gallery(url_input)
        return render_template('index.html', entries=entries, url_input=url_input)
    except NoExtractorError as e:
        return render_template('index.html', error="No Extractor found.", url_input=url_input)


@app.route('/gallery')
def gallery():
    data_json = request.args.get('data', None)
    data = json.loads(data_json)
    return render_template('gallery.html', data=data)


def main():
    app.run()


if __name__ == '__main__':
    main()
