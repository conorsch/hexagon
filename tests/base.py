"""Shared constants and helpers for the hexagon test suite.

This is the single place the suite imports test-wide settings from. The default
TemplateVM is re-imported from the application code (hexagon.qmgr.DEFAULT_TEMPLATE)
so there's exactly one place to bump it; override per-run with HEXAGON_TEST_TEMPLATE.
"""

import os
import sys

from hexagon import policy as _policy
from hexagon.qmgr import DEFAULT_TEMPLATE

# Tag applied to every VM the suite creates. The test policy (`hexagon policy
# --test`) scopes the management qube's Admin API writes to VMs carrying it, so
# teardown can only ever touch test VMs (see docs/testing.md). Single-sourced
# from the policy renderer so the suite and the grants can't drift.
TEST_TAG = _policy.TEST_TAG

# All test VMs are named "<NAME_PREFIX><n>"; teardown is doubly guarded by both
# the tag and this prefix.
NAME_PREFIX = "hexagon-test-"

# TemplateVM used for created test VMs. Defaults to the app's default; override
# for a given environment with HEXAGON_TEST_TEMPLATE=fedora-XX.
TEMPLATE = os.environ.get("HEXAGON_TEST_TEMPLATE", DEFAULT_TEMPLATE)

# How to invoke the CLI in end-to-end tests. By default we run it from the
# source checkout via `python -m hexagon` (works without installing). Set
# HEXAGON_BIN to test the installed console script instead, e.g. HEXAGON_BIN=hexagon.
HEXAGON_BIN = os.environ.get("HEXAGON_BIN")


def hexagon_cmd(*args):
    """argv for invoking the hexagon CLI (installed binary or `python -m hexagon`)."""
    if HEXAGON_BIN:
        return [HEXAGON_BIN, *args]
    return [sys.executable, "-m", "hexagon", *args]


def vm_name(n):
    """Canonical name for the nth test VM. (Not ``test_``-prefixed so pytest
    doesn't collect it as a test.)"""
    return "{}{}".format(NAME_PREFIX, n)
