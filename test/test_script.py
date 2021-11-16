#!/usr/bin/env python
# -*- coding: utf-8 -*-
import collections
import pathlib
from unittest import mock

import pytest
import yaml

import script2 as sc
from gallery_dl.job import DataJob


@pytest.mark.golden_test("data/test_extractor_*.yaml")
def test_extractor(golden):
    assert [
        DataJob(url).extractor.__class__.__name__ for url in golden["urls"]
    ] == golden.out["output"]


@pytest.mark.golden_test("data/test_items_*.yaml")
@pytest.mark.vcr()
def test_items(golden):
    job = DataJob(golden["url"])
    job.run()
    assert (
        list(
            sorted(
                job.data,
                key=lambda x: (x[0],) if isinstance(x[1], dict) else (x[0], x[1]),
            )
        )
        == golden.out["output"]
    )


@pytest.mark.golden_test("data/test_handler_*.yaml")
def test_handler(golden):
    name = golden.path.name.split("test_handler_", 1)[1].rsplit(".yaml", 1)[0]
    job = mock.Mock()
    with (
        pathlib.Path(__file__).parent / "data" / f"test_items_{name}.yaml"
    ).open() as f:
        job.data = yaml.safe_load(f)["output"]
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
