import logging
import subprocess
import time


try:
    import qubesadmin

    _HAS_QUBESADMIN = True
    _QUBESADMIN_ERR = None
except ImportError as exc:
    _HAS_QUBESADMIN = False
    _QUBESADMIN_ERR = exc


def _qubes():
    if not _HAS_QUBESADMIN:
        raise RuntimeError(
            "qubesadmin is required but not installed. "
            "Install it with: dnf install qubes-core-admin-client"
        ) from _QUBESADMIN_ERR
    return qubesadmin.Qubes()


logfmt = "%(asctime)s %(levelname)-8s %(funcName)s() %(message)s"
logging.basicConfig(format=logfmt, level=logging.DEBUG, datefmt="%Y-%m-%d %H:%M:%S")


# Single source of truth for the default TemplateVM. The test suite re-imports
# this (see tests/base.py) so there's exactly one place to bump it.
DEFAULT_TEMPLATE = "fedora-43-xfce"


CONFIG_DEFAULTS = {
    "autostart": False,
    "klass": "AppVM",
    "template": DEFAULT_TEMPLATE,
    "netvm": None,
    "label": "blue",
    "provides_network": False,
    "vcpus": "2",
}


def dom0_update_cmd():
    return ["sudo", "qubes-dom0-update", "-y"]


def vm_update_cmd(targets=(), max_concurrency=2, force=False):
    # `--targets` updates the named VMs unconditionally, so `--force-update`
    # only matters when qubes-vm-update is doing its own selection.
    cmd = ["qubes-vm-update", "--max-concurrency", str(max_concurrency)]
    if targets:
        cmd += ["--targets", ",".join(targets)]
    elif force:
        cmd += ["--force-update"]
    else:
        cmd += ["--update-if-available"]
    return cmd


class HexagonQube(object):
    # FUTURE: __init__ calls qubesadmin.Qubes() directly, so unit tests must
    # monkeypatch it (see tests/conftest.py::fake_qubes). A cleaner design would
    # inject the app, e.g. `def __init__(self, name, *, app=None, **kwargs)` with
    # `app = app or qubesadmin.Qubes()`, letting tests pass a fake without
    # patching. Deferred to keep this change scoped to the test harness.
    def __init__(self, name, *args, **kwargs):
        self.name = name
        # Don't clobber existing VM config unless explicitly requested
        if self.exists():
            self.vm = _qubes().domains[self.name]
            self.desired_config = {**kwargs}
        else:
            self.desired_config = {**CONFIG_DEFAULTS, **kwargs}
        self.pending_changes = []
        self.reboot_required = False
        self.rebuild_required = False
        new_template = self.desired_config.get("template", "")
        if new_template and new_template not in _qubes().domains:
            msg = "Target TemplateVM does not exist: {}".format(new_template)
            raise Exception(msg)

    def __repr__(self):
        s = "<HexagonQube: {}>".format(self.name)
        return s

    def exists(self):
        return self.name in _qubes().domains

    def create(self):
        if not self.exists():
            self.vm = _qubes().add_new_vm(
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
                    # DispVMs will have power state "NA" after shutdown, since they don't exist anymore.
                    if power_state in ("Halted", "NA"):
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
        self.vm = _qubes().domains[self.name]

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
                del self.pending_changes[i]

        return len(self.pending_changes) > 0

    def reboot(self, timeout=60, only_if_outdated=False):
        """
        Attempts to halt gracefully, then restart, the domU.
        If timeout is reached without confirmed shutdown,
        domain will be killed, then booted.
        """
        # Re-fetch from a fresh app so we act on the CURRENT topology. A
        # long-lived HexagonQube can predate VMs later attached to this one;
        # its cached domain list would miss them, connected_vms would read
        # empty, and ensure_halted() would take the plain-shutdown path that
        # qubesd rejects with QubesVMInUseError. A fresh object also clears the
        # memoized start_time, so uptime() reflects the reboot. (reconcile()
        # refreshes self.vm for the same reason.)
        self.vm = _qubes().domains[self.name]
        self.ensure_halted()
        self.vm.start()
        logging.debug("VM has started: {}".format(self.name))

    def open_terminal(self, grace=1):
        """
        Launch the VM's default terminal (what the app menu's "Run Terminal"
        entry does) without waiting for it to close. The launcher is detached
        from our session and stdio -- except stderr, so a qrexec "Request
        refused" stays visible -- and watched for only `grace` seconds: a
        quick non-zero exit (e.g. denied by policy when called from a
        management qube) is an error; anything still running has launched.
        Works from dom0 and from an AppVM (`wait=False` would not).
        """
        service = "qubes.StartApp+qubes-run-terminal"
        logging.debug("Opening terminal in VM: {}".format(self.name))
        proc = self.vm.run_service(
            service,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            start_new_session=True,
        )
        try:
            rc = proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            return
        if rc:
            raise subprocess.CalledProcessError(rc, service)


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
