#!/usr/bin/env python
# -*- coding: utf-8 -*-
import collections
import logging
import os
import pathlib
import typing as T
from itertools import islice
from unittest import mock

import pytest
import yaml
from pytest_golden.plugin import GoldenTestFixture

from gallery_dl import extractor
from gallery_dl import hydrus as sc
from gallery_dl.job import DataJob, config


def sorted_list(inp: T.Iterable[T.Any], **kwargs) -> T.List[T.Any]:
    return list(sorted(inp, **kwargs))


def sorted_list_set(inp: T.Iterable[T.Any]) -> T.List[T.Any]:
    return sorted_list(set(inp))


@pytest.mark.golden_test("data/test_items_*.yaml")
@pytest.mark.vcr()
def test_items(golden, caplog):
    config.load()
    url: str = golden["url"]
    if golden.get("skip"):
        pytest.skip(url)
    job = DataJob(url)
    with caplog.at_level(logging.DEBUG), open(os.devnull, "w") as f:
        job.file = f
        job.run()
    output_data = collections.defaultdict(list)
    for item in job.data:
        output_data[item[0]].append([x for x in item[1:] if x])
    try:
        output_data = {k: sorted_list_set(v) for k, v in output_data.items()}
    except TypeError:
        try:
            output_data = {
                k: sorted_list(v, key=lambda x: x[0]) for k, v in output_data.items()
            }
        except (IndexError, TypeError):
            output_data = {k: list(v) for k, v in output_data.items()}
    assert output_data == golden.out.get("output")
    debug_data = collections.defaultdict(set)
    for item in caplog.record_tuples:
        if item[0] == job.extractor.category and item[1] == logging.DEBUG:
            parts = item[2].split(",", 1)
            debug_data[parts[0]].add(next(islice(parts, 1, None), None))
    assert job.extractor.__class__.__name__ == golden.out.get("extractor")
    assert {
        k: sorted_list_set(v)
        for k, v in debug_data.items()
        if not k.startswith("Sleeping for ")
    } == golden.out.get("debug")


@pytest.mark.golden_test("data/test_handler_*.yaml")
def test_handler(golden, caplog):
    try:
        key = "test_handler_"
        if key not in golden.path.name:
            pytest.skip('"{key}" not in golden.path.name: {golden.path.name}')
        else:
            name = golden.path.name.split(key, 1)[1].rsplit(".yaml", 1)[0]
    except IndexError as err:
        logging.error("golden.path.name: {}".format(golden.path.name), exc_info=True)
        raise err
    job = mock.Mock()
    with (
        pathlib.Path(__file__).parent / "data" / f"test_items_{name}.yaml"
    ).open() as f:
        raw_data = yaml.safe_load(f)["output"]
    job.data = []
    for k, vals in raw_data.items():
        for v in vals:
            job.data.append([k] + list(v))

    with caplog.at_level(logging.DEBUG):
        res = getattr(sc, golden["handler"]).handle_job(
            job, collections.defaultdict(set)
        )
        res2 = getattr(sc, golden["handler"]).iter_queue_urls(
            job, res.get("url_set", set())
        )
    # merge res2 to res
    for k, v in res2.get("url_dict", {}).items():
        res["url_dict"][k].update(v)
    # check
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
    #  test_handler_reddit6
    debug_data = collections.defaultdict(set)
    for item in caplog.record_tuples:
        item2 = item[2]
        key = [item[0], item[1]]
        value = None
        for i2key in (" for ", ","):
            if i2key in item2:
                item2_parts = item2.split(i2key, 1)
                key.append(item2_parts[0])
                value = item2_parts[1].strip()
        if value is None:
            value = item2
        debug_data[tuple(key)].add(value)
    assert {k: sorted_list_set(v) for k, v in debug_data.items()} == golden.out.get(
        "debug"
    )


def get_golden_key(golden_obj: GoldenTestFixture, key: str) -> T.Optional[T.Any]:
    item = None
    if not (hasattr(golden_obj, "get") and (item := golden_obj.get(key))):
        return item


@pytest.mark.golden_test("data/test_url_*.yaml")
def test_url(golden):
    output_data = []
    if not (urls := get_golden_key(golden, "urls")):
        pytest.skip("no urls")
    for url in urls:
        try:
            output_data.append([url, DataJob(url).extractor.__class__.__name__])
        except Exception as err:
            logging.error("url:%s", url)
            raise err
    if not hasattr(golden, "out"):
        pytest.skip("no output data\nurls: {urls}")
    assert sorted_list(output_data) == golden.out["outputs"]
    assert sorted_list_set(golden["urls"]) == golden.out["urls"]


@pytest.mark.golden_test("data/test_replace_url_*.yaml")
def test_replace_url(golden):
    output_data = []
    urls = []
    if not (urls := get_golden_key(golden, "urls")):
        pytest.skip("no urls")
    for url in urls:
        try:
            output_data.append(
                [url, getattr(extractor, golden["extractor"]).replace_url(url)]
            )
        except Exception as err:
            logging.error("url:%s", url)
            raise err
    if not hasattr(golden, "out"):
        pytest.skip("no output data\nurls: {urls}")
    assert sorted_list(output_data) == golden.out["outputs"]
    assert sorted_list_set(golden["urls"]) == golden.out["urls"]
