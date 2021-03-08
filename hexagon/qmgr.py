import logging
import os
import subprocess
import time


import qubesadmin


logfmt = "%(asctime)s %(levelname)-8s %(funcName)s() %(message)s"
logging.basicConfig(format=logfmt, level=logging.DEBUG, datefmt="%Y-%m-%d %H:%M:%S")


CONFIG_DEFAULTS = {
    "autostart": False,
    "klass": "AppVM",
    "template": "fedora-31",
    "netvm": None,
    "label": "blue",
    "provides_network": False,
    "vcpus": "2",
}


class HexagonQube(object):
    def __init__(self, name, *args, **kwargs):
        self.name = name
        # Don't clobber existing VM config unless explicitly requested
        if self.exists():
            self.vm = qubesadmin.Qubes().domains[self.name]
            self.desired_config = {**kwargs}
        else:
            self.desired_config = {**CONFIG_DEFAULTS, **kwargs}
        self.pending_changes = []
        self.reboot_required = False
        self.rebuild_required = False
        new_template = self.desired_config.get("template", "")
        if new_template and new_template not in qubesadmin.Qubes().domains:
            msg = "Target TemplateVM does not exist: {}".format(new_template)
            raise Exception(msg)

    def __repr__(self):
        s = "<HexagonQube: {}>".format(self.name)
        return s

    def exists(self):
        return self.name in qubesadmin.Qubes().domains

    def create(self):
        if not self.exists():
            self.vm = qubesadmin.Qubes().add_new_vm(
                self.desired_config["klass"], self.name, self.desired_config["label"]
            )

    def uptime(self):
        if self.exists():
            elapsed = int(time.time()) - int(float(self.vm.start_time))
        else:
            msg = "Cannot check uptime of non-existent VM"
            raise NotImplementedError(msg)
        return elapsed

    def recreate(self):
        if self.exists():
            self.ensure_halted()
            cmd = ["qvm-remove", "-f", self.name]
            subprocess.check_call(cmd)
            time.sleep(1)
        self.create()

    def ensure_halted(self, wait=True, poll_interval=5):
        """
        Override shutdown method to block
        """
        if self.vm.is_running():
            connected_vms = [x for x in self.vm.connected_vms if x.is_running()]
            if connected_vms:
                logging.warning(
                    "Halting VM via poweroff (connected clients will be interrupted): {}".format(
                        self.vm.name
                    )
                )
                try:
                    # Ideally we'd use:
                    # self.vm.run("poweroff", user="root")
                    # but that only works in dom0, in an Admin API domU it raises:
                    # ValueError: non-default user not possible for calls from VM
                    # so instead we'll just prefix it with sudo.
                    self.vm.run("sudo poweroff")
                # There's a good chance a successful poweroff will return non-zero
                # Don't take that as a failure, since we'll poll for VM being stopped
                # later and kill it if necessary
                except subprocess.CalledProcessError:
                    pass
            else:
                logging.debug("Halting VM via shutdown: {}".format(self.vm.name))
                self.vm.shutdown()
            if wait:
                timeout = 30
                waited = 0
                while waited < timeout:
                    power_state = self.vm.get_power_state()
                    msg_f = "VM '{}' has power state {}"
                    if power_state == "Halted":
                        msg = msg_f.format(self.name, power_state)
                        logging.debug(msg)
                        break
                    else:
                        msg = msg_f.format(self.name, power_state)
                        logging.debug(msg)
                    time.sleep(poll_interval)
                    waited += poll_interval
        if self.vm.is_running():
            logging.warning("Halting VM via kill: {}".format(self.vm.name))
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
        if self.vm.klass in ("AppVM", "DispVM") and self.vm.is_running():
            for vol in self.vm.volumes.values():
                if vol.is_outdated():
                    is_outdated = True
        return is_outdated

    def reconcile(self):
        """
        Apply all outstanding config changes to VM. If VM does not exist,
        it will be created. Handles VM roughly, including rebooting despite
        attached network clients if a netvm.
        """
        # Logging is not mandatory, but calling changes_required is,
        # since it populates the pending_changes attribute.
        if not self.changes_required():
            logging.debug("{} requires no changes".format(self))
        else:
            logging.debug("{} requires changes: {}".format(self, self.pending_changes))

        # Make sure VM exists
        self.create()

        # We'll restore the original power state when done
        was_running = self.vm.is_running()

        reboot_required = False
        if self.is_outdated():
            reboot_required = True

        if any([c.reboot_required for c in self.pending_changes]):
            reboot_required = True

        if reboot_required:
            # The ensure_halted operation blocks, so we can update settings
            self.ensure_halted()

        if self.rebuild_required:
            self.recreate()

        for c in self.pending_changes:
            # logging.debug("Applying config change for {}: {}".format(self, c))
            c.apply(self.vm)

        if self.vm.autostart or was_running:
            if not self.vm.is_running():
                self.vm.start()
        else:
            if self.vm.is_running():
                self.ensure_halted()

        # Finally, update the vm attribute was latest info
        self.vm = qubesadmin.Qubes().domains[self.name]

    def changes_required(self):
        for k, v in self.desired_config.items():
            if self.exists():
                # Stringify for comparison
                actual_value = str(getattr(self.vm, k))
            else:
                actual_value = None
            if actual_value != str(self.desired_config[k]):
                pending_change = VMConfigChange(k, actual_value, v)
                self.pending_changes.append(pending_change)

        # If VM doesn't exist, "klass" will be handled by create.
        # Only if "klass" was passed to existing VM should we raise
        # unimplemented (for now).
        for i, x in enumerate(self.pending_changes):
            if x.attribute == "klass" and not self.exists():
                del (self.pending_changes[i])

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
        Upgrades packages within VM. Uses qubesctl to trigger Saltstack logic.
        Skips updates if none are available, unless force=True.
        """
        # The qubesctl/salt logic will only work in dom0.
        if not self.in_dom0:
            raise NotImplementedError

        if self.updates_available() or force:
            logging.debug("Updating packages for VM: {}".format(self.name))
            if self.name == "dom0":
                cmd = ["sudo", "qubesctl", "state.sls", "update.qubes-dom0"]
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
            cmd_output = subprocess.check_output(cmd).strip()
            logging.debug("Updated packages for VM: {}".format(cmd_output))

    def reboot(self, timeout=60, only_if_outdated=False):
        """
        Attempts to halt gracefully, then restart, the domU.
        If timeout is reached without confirmed shutdown,
        domain will be killed, then booted.
        """
        self.ensure_halted()
        self.vm.start()
        logging.debug("VM has started: {}".format(self.name))


class VMConfigChange(object):
    def __init__(self, attribute, old_value, new_value, reboot_required=False):
        self.attribute = attribute
        self.old_value = old_value
        self.new_value = new_value
        self.reboot_required = reboot_required
        if not self.reboot_required:
            if self.attribute in ("label", "template", "vcpus", "virt_mode", "kernel"):
                self.reboot_required = True

    def __repr__(self):
        s = "<VMConfigChange:{}: ".format(self.attribute)
        s += "{} -> {}, ".format(self.old_value, self.new_value)
        s += "reboot={}>".format(self.reboot_required)
        return s

    def apply(self, vm):
        if self.attribute in (
            "autostart",
            "kernel",
            "label",
            "maxmem",
            "memory",
            "provides_network",
            "template",
            "vcpus",
            "virt_mode",
        ):
            if self.attribute == "vcpus":
                self.new_value = int(self.new_value)
            setattr(vm, self.attribute, self.new_value)
        elif self.attribute == "netvm":
            if self.new_value:
                vm.netvm = self.new_value
            else:
                vm.netvm = ""
        else:
            msg = "VM property '{}' not supported".format(self.attribute)
            raise NotImplementedError(msg)
