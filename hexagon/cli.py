import argparse
import concurrent.futures
import logging
import os
import sys
import yaml


import qubesadmin
from .qmgr import HexagonQube


logfmt = "%(asctime)s %(levelname)-8s %(funcName)s() %(message)s"
logging.basicConfig(format=logfmt, level=logging.DEBUG, datefmt="%Y-%m-%d %H:%M:%S")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        default=False,
        action="store_true",
        help="Display proposed changes, but don't implement",
    )

    # Python 3.5 (dom0) doesn't support required=True
    # subparsers = parser.add_subparsers(dest='command', required=True)
    subparsers = parser.add_subparsers(dest="command")

    ls_parser = subparsers.add_parser("ls", help="ls VMs, by features or prefs")
    ls_parser.add_argument("--tags", default="", action="store", help="select VMs by tag")

    ls_parser.add_argument(
        "--template", default="", action="store", help="List only VMs based on specified TemplateVM"
    )
    ls_parser.add_argument(
        "--updatable",
        default=False,
        action="store_true",
        help="List only VMs with newer packages available",
    )
    ls_parser.add_argument(
        "--outdated",
        default=False,
        action="store_true",
        help="List only VMs whose TemplateVMs have been recently updated",
    )
    ls_parser.add_argument(
        "--property",
        action="append",
        default=[],
        type=lambda x: x.split("="),
        help="Filter by VM attribute, property, e.g. vcpus=2",
    )
    ls_parser.add_argument("vms", nargs=argparse.ZERO_OR_MORE, action="store", help="VMs to list")
    reboot_parser = subparsers.add_parser("reboot", help="reboot VMs")
    reboot_parser.add_argument(
        "vms", nargs=argparse.ZERO_OR_MORE, action="store", help="VMs to reboot"
    )
    reboot_parser.add_argument(
        "--outdated",
        default=False,
        action="store_true",
        help="Reboot only VMs whose TemplateVMs have been recently updated",
    )
    update_parser = subparsers.add_parser("update", help="update packages inside VM")
    update_parser.add_argument(
        "vms", nargs=argparse.ZERO_OR_MORE, action="store", help="VMs to update"
    )
    update_parser.add_argument(
        "--force", default=False, action="store_true", help="update even if updates-available=0"
    )
    update_parser.add_argument(
        "--max-concurrency",
        action="store",
        default=2,
        type=int,
        help="How many VMs to update in parallel",
    )
    reconcile_parser = subparsers.add_parser("reconcile", help="apply all VM config options")

    reconcile_parser.add_argument(
        "vms", nargs=argparse.ZERO_OR_MORE, action="store", help="VMs to reconcile"
    )

    reconcile_parser.add_argument(
        "--template", action="store", help="TemplateVM to set (shortcut for --property template=)"
    )
    reconcile_parser.add_argument(
        "--netvm", action="store", help="NetVM to set (shortcut for --property netvm=)"
    )
    reconcile_parser.add_argument(
        "--label", action="store", help="Label (color) to set (shortcut for --property label=)"
    )
    reconcile_parser.add_argument(
        "--property",
        action="append",
        default=[],
        type=lambda x: x.split("="),
        help="VM attribute to set, e.g. 'vcpus=1'",
    )

    shutdown_parser = subparsers.add_parser(
        "shutdown", help="Ensures specified VMs are halted (even if clients are connected)"
    )
    shutdown_parser.add_argument(
        "vms", nargs=argparse.ZERO_OR_MORE, action="store", help="VMs to shutdown"
    )
    start_parser = subparsers.add_parser("start", help="Ensures specified VMs are running")
    start_parser.add_argument(
        "vms", nargs=argparse.ZERO_OR_MORE, action="store", help="VMs to start"
    )
    args = parser.parse_args()

    # Python 3.5 compatibility requires explicit check for subcommand;
    # later versions of argparse permit use of required=True.
    if not args.command:
        msg = "subcommand required, choose one of {ls, reboot, start, shutdown, update, reconcile}"
        print(msg)
        sys.exit(1)

    return args


def load_config(config_filepath):
    cfg = {}
    if os.path.exists(config_filepath):
        with open(config_filepath, "r") as f:
            cfg = yaml.safe_load(f)
    return cfg


def reconcile_vm(args, vm_name):
    custom_config = {}
    for p in args.property:
        custom_config[p[0]] = p[1]
    # logging.debug("Reconciling custom config: {}".format(custom_config))
    cq = HexagonQube(vm_name, **custom_config)
    cq.reconcile()


def update_vm(args, vm_name):
    cq = HexagonQube(vm_name)
    cq.update(force=args.force)


def reboot_vm(args, vm_name):
    cq = HexagonQube(vm_name)
    cq.reboot()


def main():
    args = parse_args()
    q = qubesadmin.Qubes()
    vms = args.vms
    # TODO: support --max-concurrency flag, defaulting to 4
    # for "update" behavior, but for e.g. ls it's ok to raise
    n_proc = len(vms) or 4
    if args.command == "reconcile":
        # Handle helper args, maybe belongs in parse_args
        for property_alias in ("template", "netvm", "label"):
            alias_value = getattr(args, property_alias)
            if alias_value:
                args.property.append([property_alias, alias_value])
        if not vms:
            logging.error("No VMs were declared")
            # TODO: It'd be grand to read from a config file
            msg = "Reconcile must target specific VMs"
            raise NotImplementedError(msg)
        vms = [HexagonQube(x.name) for x in q.domains if x.name in vms]
        func = reconcile_vm

    elif args.command == "ls":
        logging.debug("Listing VMs...")
        if vms:
            vms = [HexagonQube(x.name) for x in q.domains if x.name in vms]
        else:
            vms = [HexagonQube(x.name) for x in q.domains]
        n_proc = len(vms) or 5
        if args.tags:
            # TODO: support csv tags
            vms = [x for x in vms if args.tags in x.vm.tags]
        if args.template:
            vms = [x for x in vms if getattr(x.vm, "template", "") == args.template]
        if args.updatable:
            vms = [x for x in vms if x.vm.features.get("updates-available", "0") == "1"]
        if args.outdated:
            vms = [x for x in vms if x.is_outdated()]
        if args.property:
            for p in args.property:
                k, v = p[0], p[1]
                vms = [x for x in vms if hasattr(x.vm, k)]
                if v.startswith("!"):
                    v = v[1:]
                    vms = [x for x in vms if str(getattr(x.vm, k, "")) != v]
                else:
                    vms = [x for x in vms if str(getattr(x.vm, k, "")) == v]

        for vm in vms:
            print(vm.name)
        sys.exit(0)

    elif args.command == "reboot":
        if vms:
            vms = [HexagonQube(x.name) for x in q.domains if x.name in vms]
        if args.outdated and vms:
            vms = [x for x in vms if x.is_outdated()]
        elif args.outdated and not vms:
            vms = [HexagonQube(x.name) for x in q.domains]
            vms = [x for x in vms if x.is_outdated()]
        vms = [x.name for x in vms]
        func = reboot_vm

    elif args.command == "update":
        n_proc = args.max_concurrency
        if not vms:
            vms = [x for x in q.domains if x.features.get("updates-available", "0") == "1"]
            vms = [x.name for x in vms]
        # TODO: handle dom0 separately, before all domUs
        func = update_vm

    elif args.command == "shutdown":
        requested_vms = len(vms)
        if requested_vms > 0:
            vms = [HexagonQube(x.name) for x in q.domains if x.name in vms]
            if len(vms) != requested_vms:
                msg = "Some VMs could not be found"
                raise Exception(msg)
        else:
            logging.error("No VMs were declared")
            # TODO: It'd be grand to read from a config file
            msg = "Shutdown must target specific VMs"
            raise NotImplementedError(msg)

        def f(args, x):
            x.ensure_halted

        func = f

    elif args.command == "start":
        requested_vms = len(vms)
        if requested_vms > 0:
            vms = [HexagonQube(x.name) for x in q.domains if x.name in vms]
            if len(vms) != requested_vms:
                msg = "Some VMs could not be found"
                raise Exception(msg)
        else:
            logging.error("No VMs were declared")
            # TODO: It'd be grand to read from a config file
            msg = "Start must target specific VMs"
            raise NotImplementedError(msg)

        def f(args, x):
            x.vm.start()

        func = f
    else:
        msg = "Action not supported: {}".format(args.command)
        raise NotImplementedError(msg)

    if args.dry_run:
        logging.debug("Would {} VMs: {}".format(args.command, vms))
        sys.exit(0)

    logging.debug("Performing {} of VMs: {}".format(args.command, vms))
    with concurrent.futures.ThreadPoolExecutor(max_workers=n_proc) as executor:
        results = list(map(lambda x: executor.submit(func, args, x), vms))

    errors = 0
    for i, r in enumerate(results):
        vm = vms[i]
        try:
            r.result()
            logging.debug("VM operation {} completed: {}".format(args.command, vm))
        except Exception as e:
            errors += 1
            logging.debug("VM operation {} failed: {}, error: {}".format(args.command, vm, repr(e)))

    logging.debug("All VM {} operations finished, with {} errors".format(args.command, errors))
    if errors:
        sys.exit(1)
