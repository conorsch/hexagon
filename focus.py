#!/usr/bin/env python3
"""
Utilty script to halt all but "essential" VMs
"""

import qubesadmin
import argparse


q = qubesadmin.Qubes()
vms = [x for x in q.domains if x.name != "dom0"]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "vms_to_allow", default=[], action="store", help="VMs to omit from shutdown"
    )


def ensure_autostart_running():
    autostart_vms = [x for x in vms if x.autostart]
    for vm in autostart_vms:
        print("Starting VM: " + vm.name)
        vm.start()


def shutdown_unessential_vms():
    """
    Halts anything other than essential
    """
    try_again = False
    for vm in vms:
        if not vm.autostart:
            if "cli" not in vm.tags:
                if vm.is_running():
                    print("Halting VM: " + vm.name)
                    try:
                        vm.shutdown()
                    except qubesadmin.exc.QubesVMError:
                        try_again = True
                        pass

    if try_again:
        shutdown_unessential_vms()


if __name__ == "__main__":
    args = parse_args()
    ensure_autostart_running()
    shutdown_unessential_vms()
