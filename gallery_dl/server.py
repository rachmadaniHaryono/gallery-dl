#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json

from .job import DataJob
from .exception import NoExtractorError


from flask import Flask, render_template, request


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

@app.route('/')
def index():
    url_input = request.args.get('url', None)
    if url_input is None:
        return render_template('index.html')
    try:
        job = CustomDataJob(url_input)
        entries = job.get_data()[2:]
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
