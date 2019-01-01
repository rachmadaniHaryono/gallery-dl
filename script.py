from types import SimpleNamespace
from unittest.mock import patch, Mock
import os

import click
from flask.cli import FlaskGroup
from flask import (
    Flask,
    jsonify,
    request,
)

from gallery_dl import main, option
from gallery_dl.job import DataJob

def get_json():
    data = None
    parser = option.build_parser()
    args = parser.parse_args()
    args.urls = request.args.getlist('url')
    if not args.urls:
        return jsonify({'error': 'No url(s)'})
    args.list_data = True

    class CustomClass:
        data = []

        def run(self):
            dj = DataJob(*self.data_job_args, **self.data_job_kwargs)
            dj.run()
            self.data.append({
                'args': self.data_job_args,
                "kwargs": self.data_job_kwargs,
                'data': dj.data
            })

        def DataJob(self, *args, **kwargs):
            self.data_job_args = args
            self.data_job_kwargs = kwargs
            retval = SimpleNamespace()
            retval.run = self.run
            return retval

    c1 = CustomClass()
    with patch('gallery_dl.option.build_parser') as m_bp, \
            patch('gallery_dl.job.DataJob', side_effect=c1.DataJob) as m_jt:
        #  m_option.return_value.parser_args.return_value = args
        m_bp.return_value.parse_args.return_value = args
        m_jt.__name__ = 'DataJob'
        main()
        data = c1.data
    return jsonify({'data': data, 'urls': args.urls})

def create_app(script_info=None):
    """create app."""
    app = Flask(__name__)
    app.add_url_rule(
        '/api/json', 'gallery_dl_json', get_json)
    return app


@click.group(cls=FlaskGroup, create_app=create_app)
def cli():
    """This is a script for application."""
    pass


if __name__ == '__main__':
    cli()
