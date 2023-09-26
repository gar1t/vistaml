# SPDX-License-Identifier: Apache-2.0

from typing import *
from .types import *

import functools
import logging
import os

from . import sys_config

from .opref_util import decode_opref

from .run_util import run_name_for_id

log = logging.getLogger(__name__)

RunFilter = Callable[[Run], bool]


def list_runs(
    root: Optional[str] = None,
    sort: Optional[str] = None,
    filter: Optional[RunFilter] = None,
):
    root = root or sys_config.runs_home()
    filter = filter or _all_runs_filter
    runs = [run for run in _iter_runs(root) if filter(run)]
    if not sort:
        return runs
    return runs
    ##return sorted(runs, key=_run_sort_key(sort))


def _all_runs_filter(run: Run):
    return True


def _iter_runs(root: str):
    try:
        names = set(os.listdir(root))
    except OSError:
        names: Set[str] = set()
    for name in names:
        if not name.endswith(".meta"):
            continue
        meta_dir = os.path.join(root, name)
        opref_filename = os.path.join(meta_dir, "opref")
        if not os.path.exists(opref_filename):
            continue
        try:
            opref = _load_opref(opref_filename)
        except (OSError, ValueError) as e:
            pass
        else:
            run_id = name
            run_dir = meta_dir[:-5]
            run_name = run_name_for_id(run_id)
            yield Run(run_id, opref, meta_dir, run_dir, run_name)


def _load_opref(filename: str):
    with open(filename) as f:
        return decode_opref(f.read())


# def _run_sort_key(sort: str):
#     def cmp(a: Run, b: Run):
#         return _run_cmp(a, b, sort)

#     return functools.cmp_to_key(cmp)


# def _run_cmp(a: Run, b: Run, sort: str):
#     for attr in sort:
#         attr_cmp = _run_attr_cmp(a, b, attr)
#         if attr_cmp != 0:
#             return attr_cmp
#     return 0


# def _run_attr_cmp(a: Run, b: Run, attr: str):
#     if attr.startswith("-"):
#         attr = attr[1:]
#         rev = -1
#     else:
#         rev = 1
#     x_val = run_attr(a, attr)
#     if x_val is None:
#         return -rev
#     y_val = run_attr(b, attr)
#     if y_val is None:
#         return rev
#     return rev * ((x_val > y_val) - (x_val < y_val))
