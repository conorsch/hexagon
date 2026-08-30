import argparse
import concurrent.futures
import logging
import os
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version as _pkg_version

import yaml

from .qmgr import HexagonQube, dom0_update_cmd, vm_update_cmd
from . import policy as policy_mod
from . import preflight


def _resolve_version():
    # Prefer the version baked in at build time (see flake.nix); the noarch
    # RPM ships bare .py files without dist-info, so importlib.metadata can't
    # see it. Fall back through dist-info, then a source checkout's
    # pyproject.toml, before giving up.
    try:
        from hexagon._version import VERSION

        return VERSION
    except ImportError:
        pass

    try:
        return _pkg_version("hexagon")
    except PackageNotFoundError:
        pass

    import tomllib

    here = os.path.dirname(os.path.abspath(__file__))
    try:
        with open(os.path.join(here, "..", "pyproject.toml"), "rb") as f:
            return tomllib.load(f)["project"]["version"]
    except (FileNotFoundError, KeyError, tomllib.TOMLDecodeError):
        pass

    return "0.0.0+unknown"


VERSION = _resolve_version()


logfmt = "%(asctime)s %(levelname)-8s %(funcName)s() %(message)s"
logging.basicConfig(format=logfmt, level=logging.DEBUG, datefmt="%Y-%m-%d %H:%M:%S")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--version", action="version", version="%(prog)s {version}".format(version=VERSION)
    )
    parser.add_argument(
        "--dry-run",
        default=False,
        action="store_true",
        help="Display proposed changes, but don't implement",
    )

    # Python 3.5 (dom0) doesn't support required=True
    # subparsers = parser.add_subparsers(dest='command', required=True)
    subparsers = parser.add_subparsers(dest="command")

    # Shared by all VM-targeting subcommands: select VMs by tag, instead of
    # (or in addition to) naming them explicitly.
    tags_parser = argparse.ArgumentParser(add_help=False)
    tags_parser.add_argument("--tags", default="", action="store", help="select VMs by tag")

    ls_parser = subparsers.add_parser(
        "ls", parents=[tags_parser], help="ls VMs, by features or prefs"
    )
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
    reboot_parser = subparsers.add_parser("reboot", parents=[tags_parser], help="reboot VMs")
    reboot_parser.add_argument(
        "vms", nargs=argparse.ZERO_OR_MORE, action="store", help="VMs to reboot"
    )
    reboot_parser.add_argument(
        "--outdated",
        default=False,
        action="store_true",
        help="Reboot only VMs whose TemplateVMs have been recently updated",
    )
    reboot_parser.add_argument(
        "-t",
        "--terminal",
        default=False,
        action="store_true",
        help="open a terminal in each VM once it's back up (does not wait for it to close)",
    )
    update_parser = subparsers.add_parser(
        "update", parents=[tags_parser], help="update packages inside VM"
    )
    update_parser.add_argument(
        "vms", nargs=argparse.ZERO_OR_MORE, action="store", help="VMs to update"
    )
    update_parser.add_argument(
        "--force",
        default=False,
        action="store_true",
        help="update even if updates-available=0 (qubes-vm-update --force-update)",
    )
    # dom0/domU scoping. Naming VMs already implies a scope (see main), so
    # these are shorthands: `--vms` is `--skip-dom0`; `--dom0` is `dom0` alone.
    scope = update_parser.add_mutually_exclusive_group()
    scope.add_argument(
        "--skip-dom0",
        "--vms",
        "--domus",
        dest="skip_dom0",
        default=False,
        action="store_true",
        help="only update domUs; do not run qubes-dom0-update",
    )
    scope.add_argument(
        "--dom0",
        dest="only_dom0",
        default=False,
        action="store_true",
        help="only run qubes-dom0-update; skip domUs",
    )
    update_parser.add_argument(
        "--max-concurrency",
        action="store",
        default=5,
        type=int,
        help="How many VMs to update in parallel",
    )
    reconcile_parser = subparsers.add_parser(
        "reconcile", parents=[tags_parser], help="apply all VM config options"
    )

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
        "shutdown",
        parents=[tags_parser],
        help="Ensures specified VMs are halted (even if clients are connected)",
    )
    shutdown_parser.add_argument(
        "vms", nargs=argparse.ZERO_OR_MORE, action="store", help="VMs to shutdown"
    )
    start_parser = subparsers.add_parser(
        "start", parents=[tags_parser], help="Ensures specified VMs are running"
    )
    start_parser.add_argument(
        "vms", nargs=argparse.ZERO_OR_MORE, action="store", help="VMs to start"
    )

    policy_parser = subparsers.add_parser(
        "policy",
        help="Print the dom0 qrexec policy for a Qubes 4.3 Ansible ManagementVM",
    )
    policy_parser.add_argument(
        "--test",
        default=False,
        action="store_true",
        help="render the integration-test policy (30-hexagon-test.policy) instead; "
        "of the options below only --admin-qube applies",
    )
    policy_parser.add_argument(
        "--admin-tag",
        default=policy_mod.DEFAULT_ADMIN_TAG,
        help="Tag on qube(s) allowed to drive Ansible (grant source) [default: %(default)s]",
    )
    policy_parser.add_argument(
        "--target-tag",
        default=policy_mod.DEFAULT_TARGET_TAG,
        help="Tag on managed qubes (grant target) [default: %(default)s]",
    )
    policy_parser.add_argument(
        "--admin-qube",
        dest="admin_qubes",
        action="append",
        default=[],
        metavar="QUBE",
        help="Admin qube name whose disp-mgmt VMs get created-by grants; "
        "repeatable [default: {}]".format(" ".join(policy_mod.DEFAULT_ADMIN_QUBES)),
    )
    policy_parser.add_argument(
        "--sys-vm",
        dest="sys_vms",
        action="append",
        default=[],
        metavar="VM",
        help="sys-* qube the qube module must read; repeatable [default: {}]".format(
            " ".join(policy_mod.DEFAULT_SYS_VMS)
        ),
    )
    policy_parser.add_argument(
        "--mgmt-dispvm",
        default=policy_mod.DEFAULT_MGMT_DISPVM,
        help="Management DispVM template qubes_proxy derives targets from [default: %(default)s]",
    )

    args = parser.parse_args()

    # Python 3.5 compatibility requires explicit check for subcommand;
    # later versions of argparse permit use of required=True.
    if not args.command:
        msg = (
            "subcommand required, choose one of "
            "{ls, reboot, start, shutdown, update, reconcile, policy}"
        )
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


def reboot_vm(args, vm_name):
    cq = HexagonQube(vm_name)
    cq.reboot()
    if args.terminal:
        cq.open_terminal()


def main():
    args = parse_args()

    # `policy` is pure text generation -- no Admin API needed, so it runs in any
    # AppVM (or dom0) without qrexec grants. Emit and exit before touching Qubes.
    if args.command == "policy":
        if args.test:
            body = policy_mod.render_test_policy(admin_qubes=args.admin_qubes or None)
        else:
            body = policy_mod.render_policy(
                admin_tag=args.admin_tag,
                target_tag=args.target_tag,
                admin_qubes=args.admin_qubes or None,
                sys_vms=args.sys_vms or None,
                mgmt_dispvm=args.mgmt_dispvm,
            )
        sys.stdout.write(body)
        sys.exit(0)

    # Everything below needs the Admin API. Bail with a specific reason if this
    # host, interpreter, or qrexec policy can't provide it (see preflight.py).
    q = preflight.run()
    vms = args.vms
    # Tag selection: no names given -> target all tagged VMs; names given ->
    # narrow them to the tagged subset. `ls` applies the same filter itself.
    # TODO: support csv tags
    if args.tags and args.command != "ls":
        tagged = [x.name for x in q.domains if args.tags in x.tags]
        vms = [v for v in vms if v in tagged] if vms else tagged
        if not vms:
            logging.error("No VMs matched tag: {}".format(args.tags))
            sys.exit(1)
    n_proc = len(vms) or 4
    if args.command == "reconcile":
        # Handle helper args, maybe belongs in parse_args
        for property_alias in ("template", "netvm", "label"):
            alias_value = getattr(args, property_alias)
            if alias_value:
                args.property.append([property_alias, alias_value])
        if not vms:
            logging.error("No VMs were declared")
            msg = "Reconcile must target specific VMs"
            raise NotImplementedError(msg)
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
        # Delegates entirely to the upstream updaters: qubes-dom0-update for
        # dom0, and a single qubes-vm-update call which handles its own target
        # selection and parallelism. Naming specific VMs skips dom0.
        targets = [v for v in vms if v != "dom0"]
        if args.only_dom0 and targets:
            logging.error("--dom0 cannot be combined with domU selection: {}".format(targets))
            sys.exit(1)
        cmds = []
        if not args.skip_dom0 and (not vms or "dom0" in vms):
            cmds.append(dom0_update_cmd())
        if not args.only_dom0 and (targets or not vms):
            cmds.append(vm_update_cmd(targets, args.max_concurrency, force=args.force))
        errors = 0
        for cmd in cmds:
            if args.dry_run:
                logging.debug("Would run: {}".format(" ".join(cmd)))
                continue
            logging.debug("Running: {}".format(" ".join(cmd)))
            try:
                subprocess.check_call(cmd)
            except subprocess.CalledProcessError as e:
                errors += 1
                logging.error("Update command failed: {}".format(repr(e)))
        sys.exit(1 if errors else 0)

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
            x.ensure_halted()

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


def qvm_reboot_main():
    os.execvp("hexagon", ["hexagon", "reboot"] + sys.argv[1:])
