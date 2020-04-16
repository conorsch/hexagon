import argparse
import concurrent.futures
import qubesadmin
import yaml

from itertools import repeat

import logging
import coloredlogs

from .qmgr import CustomQube


# TODO: consider setting env var
colored_logs_field_styles = {"funcName": {"color": "cyan"}}
colored_logs_field_styles = {
    **coloredlogs.DEFAULT_FIELD_STYLES,
    **colored_logs_field_styles,
}

logfmt = "%(asctime)s %(levelname)-8s %(funcName)s() %(message)s"
logging.basicConfig(format=logfmt, level=logging.DEBUG, datefmt="%Y-%m-%d %H:%M:%S")
coloredlogs.install(level="DEBUG", field_styles=colored_logs_field_styles, fmt=logfmt)

q = qubesadmin.Qubes()


CONFIG_DEFAULTS = {
    "autostart": False,
    "klass": "AppVM",
    "template": "fedora-30",
    "netvm": None,
    "label": "blue",
    "provides_network": False,
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "vms", nargs="?", type=str, action="store", help="VMs to configure"
    )
    parser.add_argument(
        "--template",
        default=CONFIG_DEFAULTS["template"],
        action="store",
        help="TemplateVM to set",
    )
    parser.add_argument(
        "--netvm", default=CONFIG_DEFAULTS["netvm"], action="store", help="NetVM to set"
    )
    parser.add_argument(
        "--config-file",
        default="qubes.yml",
        type=str,
        action="store",
        help="Load YAML config from",
    )
    parser.add_argument(
        "--label",
        default=CONFIG_DEFAULTS["label"],
        action="store",
        help="Label (color) to set",
    )
    parser.add_argument(
        "--dry-run",
        default=False,
        action="store_true",
        help="Display proposed changes, but don't implement",
    )
    args = parser.parse_args()
    return args


def load_config(config_filepath):
    with open(config_filepath, "r") as f:
        y = yaml.safe_load(f)
    return y


def reconcile_vm(args, vm_name):
    custom_config = merge_vm_config(args, vm_name)
    cq = CustomQube(vm_name, **custom_config)
    cq.reconcile()


def merge_vm_config(args, vm_name):
    cfg = load_config(args.config_file)
    vm_cfg = {}
    cfg_vm_defaults = cfg["qubes_vms"].get("_defaults", {})
    cfg_vm_overrides = cfg["qubes_vms"].get(vm_name, {})
    # Merge dicts, with overrides winning
    vm_cfg = {**cfg_vm_defaults, **cfg_vm_overrides}
    return vm_cfg


def main():
    args = parse_args()
    vms = args.vms
    if not vms:
        logging.debug("No VMs were declared")
        vms = []
        for k, v in load_config(args.config_file).get("qubes_vms", {}).items():
            if k == "_defaults":
                continue
            vms.append(k)

    logging.debug("Proceeding with vms: {}".format(vms))
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
    executor.map(reconcile_vm, repeat(args), vms)
    executor.shutdown()
