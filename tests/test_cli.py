"""End-to-end CLI tests against the live Qubes Admin API.

The CLI is invoked as a subprocess (installed `hexagon`, or `python -m hexagon`
from a source checkout). Assertions only reference VMs the suite created.

Note: `hexagon ls` enumerates *all* domains and reads each one's tags, so this
path needs read-only Admin API access to every VM (the policy grants global
admin.vm.{List,property.Get,tag.*,feature.Get}); writes stay tag-scoped.
"""

import subprocess

import pytest

from .base import TEST_TAG, hexagon_cmd, vm_name

pytestmark = pytest.mark.integration


def _run(*args):
    return subprocess.check_output(hexagon_cmd(*args), text=True).rstrip()


def test_ls_by_tag_lists_created_vm(make_test_vm):
    name = vm_name(1)
    make_test_vm(name)
    listed = _run("ls", "--tags", TEST_TAG).split("\n")
    assert name in listed


def test_ls_by_name_returns_only_that_vm(make_test_vm):
    name = vm_name(1)
    make_test_vm(name)
    assert _run("ls", name) == name
