#!/usr/bin/env python3
"""
Utility script to reboot Qubes domains. Attempts
to perform a graceful shutdown, kills if shutdown fails,
then starts up. Inspiration for the timeout logic taken
from qubesadmin.tools.qvm_shutdown.main.
"""
import time
import qubesadmin

import subprocess
import logging
import os

# import coloredlogs

# TODO: consider setting env var
# colored_logs_field_styles = {"funcName": {"color": "cyan"}}
# colored_logs_field_styles = {
#    **coloredlogs.DEFAULT_FIELD_STYLES,
#    **colored_logs_field_styles,
# }

logfmt = "%(asctime)s %(levelname)-8s %(funcName)s() %(message)s"
logging.basicConfig(format=logfmt, level=logging.DEBUG, datefmt="%Y-%m-%d %H:%M:%S")
# coloredlogs.install(level="DEBUG", field_styles=colored_logs_field_styles, fmt=logfmt)


CONFIG_DEFAULTS = {
    "autostart": False,
    "klass": "AppVM",
    "template": "fedora-30",
    "netvm": None,
    "label": "blue",
    "provides_network": False,
}


class CustomQube(object):
    def __init__(self, name, *args, **kwargs):
        self.name = name
        self.desired_config = {**CONFIG_DEFAULTS, **kwargs}
        self.outdated = False
        self.pending_changes = []
        self.reboot_required = False
        self.rebuild_required = False
        if self.exists():
            self.vm = qubesadmin.Qubes().domains[self.name]

    def __repr__(self):
        s = "<CustomQube: {}>".format(self.name)
        return s

    def exists(self):
        return self.name in qubesadmin.Qubes().domains

    def create(self):
        if not self.exists():
            self.vm = qubesadmin.Qubes().add_new_vm(
                self.desired_config["klass"], self.name, self.desired_config["label"]
            )

    def recreate(self):
        if self.exists():
            self.ensure_halted()
            cmd = ["qvm-remove", "-f", self.name]
            subprocess.check_call(cmd)
            time.sleep(1)
        self.create()

    def ensure_halted(self, wait=True):
        """
        Override shutdown method to block
        """
        if self.vm.is_running():
            logging.debug("Shutting down VM: {}".format(self.vm.name))
            self.vm.shutdown()
            if wait:
                timeout = 30
                waited = 0
                while waited < timeout:
                    power_state = self.vm.get_power_state()
                    if power_state == "Halted":
                        break
                    else:
                        logging.debug(
                            "VM {} has power state {}, sleeping".format(
                                self.name, power_state
                            )
                        )
                        time.sleep(1)
                        waited += 1
                        continue
        if self.vm.is_running():
            logging.debug("Killing VM: {}".format(self.vm.name))
            self.vm.kill()

    def is_outdated(self):
        """
        Determine whether VM should be rebooted in order to apply updates.
        Mostly relevant for an AppVM, to check whether its TemplateVM has
        been updated.

        Adapted from:
        https://github.com/QubesOS/qubes-manager/blob/da2826db20fa852403240a45b3906a6c54b2fe33/qubesmanager/table_widgets.py#L402-L406
        """
        is_outdated = False
        for vol in self.vm.volumes.values():
            if vol.is_outdated():
                is_outdated = True
        return is_outdated

    def reconcile(self):
        """
        """
        logging.debug("Processing reconcile for {}".format(self.name))
        if not self.changes_required():
            logging.debug("VM requires no changes: {}".format(self.name))
            return
        else:
            logging.debug("Proceeding with reconcile for: {}".format(self.name))

        self.create()

        reboot_required = False
        if self.is_outdated():
            logging.debug("VM {} rebooted required: volumes".format(self.name))
            reboot_required = True

        logging.debug("Checking pending changes...")
        for c in self.pending_changes:
            if c.reboot_required:
                reboot_required = True
            logging.debug("VM {} pending change: {}".format(self.name, c))

        if self.rebuild_required:
            self.recreate()

        if reboot_required:
            # Blocks
            self.ensure_halted()

        self.vm.label = self.desired_config["label"]
        self.vm.autostart = self.desired_config["autostart"]
        logging.debug("NETVM SETTING: {}".format(self.desired_config["netvm"]))

        if self.desired_config["netvm"]:
            self.vm.netvm = self.desired_config["netvm"]
        else:
            self.vm.netvm = ""

        if self.vm.autostart:
            if not self.vm.is_running():
                self.vm.start()
        else:
            if self.vm.is_running():
                self.ensure_halted()

        # Finally, update the vm attribute was latest info
        self.vm = qubesadmin.Qubes().domains[self.name]

    def changes_required(self):
        if not self.exists():
            return True

        for k, v in self.desired_config.items():
            # Stringify for comparison
            actual_value = str(getattr(self.vm, k))
            if actual_value != str(self.desired_config[k]):
                reboot_required = False
                if k in ("template", "vcpus"):
                    reboot_required = True
                pending_change = VMConfigChange(
                    k, actual_value, v, reboot_required=reboot_required
                )
                self.pending_changes.append(pending_change)

        return len(self.pending_changes) > 0

    def updates_available(self):
        return self.vm.features.get("updates-available", False)

    def in_dom0(self):
        """
        Checks whether current execution is within dom0.
        """
        result = False
        cmd = ["qubesctl", "--help"]
        try:
            subprocess.check_call(cmd, stdout=os.devnull, stderr=os.devnull)
            result = True
        except subprocess.CalledProcessError:
            pass
        return result

    def update(self, force=False):
        """
        Upgrades packages within VM.
        """
        # Will only work in dom0
        if not self.in_dom0:
            raise NotImplementedError

        if self.updates_available() or force:
            logging.debug("Updating packages for VM: {}".format(self.name))
            if self.name == "dom0":
                cmd = [
                    "sudo",
                    "qubesctl",
                    "state.sls",
                    "update.qubes-dom0",
                ]
            else:
                cmd = [
                    "sudo",
                    "qubesctl",
                    "--skip-dom0",
                    "--target",
                    self.name,
                    "state.sls",
                    "update.qubes-vm",
                ]
            subprocess.check_call(cmd)


class VMConfigChange(object):
    def __init__(self, attribute, old_value, new_value, reboot_required=False):
        self.attribute = attribute
        self.old_value = old_value
        self.new_value = new_value
        self.reboot_required = reboot_required

    def __repr__(self):
        s = "<VMConfigChange:{}: ".format(self.attribute)
        s += "{} -> {}, ".format(self.old_value, self.new_value)
        s += "reboot={}>".format(self.reboot_required)
        return s
