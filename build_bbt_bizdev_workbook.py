from __future__ import annotations

import sys
import types

from bbt_bizdev.models import *
from bbt_bizdev.config import *
from bbt_bizdev.http import *
from bbt_bizdev.text import *
from bbt_bizdev.adapters.search import *
from bbt_bizdev.adapters.jobs import *
from bbt_bizdev.adapters.accelerators import *
from bbt_bizdev.adapters.generic import *
from bbt_bizdev.adapters.university import *
from bbt_bizdev.adapters.vc import *
from bbt_bizdev.pipeline import *
from bbt_bizdev.workbook import *

import bbt_bizdev.config as _config
import bbt_bizdev.http as _http
import bbt_bizdev.text as _text
import bbt_bizdev.adapters.search as _search
import bbt_bizdev.adapters.jobs as _jobs
import bbt_bizdev.adapters.accelerators as _accelerators
import bbt_bizdev.adapters.generic as _generic
import bbt_bizdev.adapters.university as _university
import bbt_bizdev.adapters.vc as _vc
import bbt_bizdev.pipeline as _pipeline
import bbt_bizdev.workbook as _workbook

_PATCH_MODULES = [_config, _http, _text, _search, _jobs, _accelerators, _generic, _university, _vc, _pipeline, _workbook]


def _propagate(name, value):
    for module in _PATCH_MODULES:
        if hasattr(module, name):
            setattr(module, name, value)


class _CompatModule(types.ModuleType):
    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name not in {"_PATCH_MODULES"}:
            _propagate(name, value)


sys.modules[__name__].__class__ = _CompatModule


if __name__ == "__main__":
    main()
