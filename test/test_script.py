#!/usr/bin/env python
# -*- coding: utf-8 -*-
import collections
import logging
import os
import pathlib
import typing as T
from unittest import mock

import pytest
import yaml

import script2 as sc
from gallery_dl import extractor
from gallery_dl.job import DataJob, config


def sorted_list(inp: T.Iterable[T.Any]) -> T.List[T.Any]:
    return list(sorted(inp))


@pytest.mark.golden_test("data/test_extractor_*.yaml")
def test_extractor(golden):
    assert [
        DataJob(url).extractor.__class__.__name__ for url in golden["urls"]
    ] == golden.out["output"]




@pytest.mark.golden_test("data/test_items_*.yaml")
@pytest.mark.vcr()
def test_items(golden, caplog):
    config.load()
    url: str = golden["url"]
    if golden.get("skip"):
        pytest.skip(url)
    job = DataJob(url)
    job.file = open(os.devnull, "w")
    with caplog.at_level(logging.DEBUG):
        job.run()
    output_data = collections.defaultdict(list)
    for item in job.data:
        output_data[item[0]].append([x for x in item[1:] if x])
    try:
        output_data = {k: list(sorted(v)) for k, v in output_data.items()}
    except TypeError:
        output_data = {k: list(v) for k, v in output_data.items()}
    assert output_data == golden.out.get("output")
    debug_data = collections.defaultdict(set)
    for item in caplog.record_tuples:
        if item[0] == job.extractor.category and item[1] == logging.DEBUG:
            parts = item[2].split(",", 1)
            debug_data[parts[0]].add(parts[1])
    assert {k: list(sorted(v)) for k, v in debug_data.items()} == golden.out.get(
        "debug"
    )


@pytest.mark.golden_test("data/test_handler_*.yaml")
def test_handler(golden):
    name = golden.path.name.split("test_handler_", 1)[1].rsplit(".yaml", 1)[0]
    job = mock.Mock()
    with (
        pathlib.Path(__file__).parent / "data" / f"test_items_{name}.yaml"
    ).open() as f:
        raw_data = yaml.safe_load(f)["output"]
    job.data = []
    for k, vals in raw_data.items():
        for v in vals:
            job.data.append([k] + list(v))
    handler_func = getattr(sc, golden["handler"]).handle_job
    res = handler_func(job, collections.defaultdict(set), ())
    sort_list = lambda x: list(sorted(x))
    for item in res.items():
        if item[0] == "url_dict":
            assert (
                sort_list([k, sort_list(v)] for k, v in item[1].items())
                == golden.out[item[0]]
            )
        elif item[1]:
            # only check when there is value
            assert item[1] == golden.out[item[0]]


@pytest.mark.golden_test("data/test_url_*.yaml")
def test_url(golden):
    output_data = []
    for url in golden["urls"]:
        try:
            output_data.append([url, DataJob(url).extractor.__class__.__name__])
        except Exception as err:
            logging.error("url:%s", url)
            raise err
    assert sorted_list(output_data) == golden.out["outputs"]
    assert sorted_list(set(golden["urls"])) == golden.out["urls"]


@pytest.mark.golden_test("data/test_replace_url_*.yaml")
def test_replace_url(golden):
    output_data = []
    for url in golden["urls"]:
        try:
            output_data.append(
                [url, getattr(extractor, golden["extractor"]).replace_url(url)]
            )
        except Exception as err:
            logging.error("url:%s", url)
            raise err
    assert sorted_list(output_data) == golden.out["outputs"]
    assert sorted_list(set(golden["urls"])) == golden.out["urls"]
