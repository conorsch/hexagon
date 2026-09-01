# hexagon

A rough-and-tumble CLI tool for managing [Qubes OS](https://qubes-os.org) VMs.

## Why?

Because I wanted these commands:


  * `qvm-reboot`
  * `qvm-update`

And they don't exist. Rather than trample on the `qvm-*` namespace, it seemed more prudent
to create a tool to provide that functionality. It was also a splendid opportunity
to learn the [Qubes Admin API in Python](https://dev.qubes-os.org/projects/core-admin-client/en/latest/qubesadmin.html#module-qubesadmin.app)!

## Usage
Here's how to use it:

```
# List all VMs with known available package updates
hexagon ls --updatable

# List all VMs with recently updated templates
hexagon ls --outdated

# Reboot particular VM (even if networked clients are attached!)
hexagon reboot sys-whonix

# Reboot a VM, then open a terminal in it once it's back up
# (from a management qube this needs a `qubes.StartApp +qubes-run-terminal` grant)
hexagon reboot -t work

# Open a terminal in one or more VMs (starts the VM if halted)
hexagon terminal work personal

# Modify TemplateVM settings for several VMs at once (e.g. fedora-30 -> fedora-34)
hexagon reconcile --template fedora-34 sys-usb sys-net sys-firewall

# Upgrade packages within a particular VM
hexagon update fedora-34

# Upgrade packages for all VMs with pending updates
hexagon update

# Upgrade only domUs (skip dom0), or only dom0
hexagon update --vms
hexagon update --dom0

# Shut down all VMs carrying a given tag (works on all VM subcommands)
hexagon shutdown --tags foo

# Print the dom0 qrexec policy for a Qubes 4.3 Ansible ManagementVM
hexagon policy

# ...or the one the integration tests need, with this qube as the source
hexagon policy --test
```

### Ansible ManagementVM policy

`hexagon policy` renders the dom0 qrexec policy that lets a management qube
drive [Qubes 4.3 Ansible](https://github.com/QubesOS/qubes-ansible) (the
`qubesos.core` / `qubesos.security` collections). It's pure text generation —
no Admin API — so it runs in any AppVM; review the output, then apply it in
dom0:

```
qvm-run -p fleet 'hexagon policy' \
  | sudo tee /etc/qubes/policy.d/30-mgmtvm.policy
qubes-policy-lint /etc/qubes/policy.d/30-mgmtvm.policy
```

The scheme is **tag-based**, so membership is a `qvm-tags` away:

- **`@tag:hexagon-admin`** — qube(s) allowed to drive Ansible (grant source).
  Enroll a MgmtVM with `qvm-tags <vm> add hexagon-admin`; untagging is the
  fleet-wide kill-switch.
- **`@tag:hexagon`** — managed qubes. Opt one in with
  `qvm-tags <vm> add hexagon`; untag to exclude it. Management is never coupled
  to concrete names or creation provenance. The **same tag permits cloning**: to
  make a TemplateVM cloneable (for StandaloneVM / new-TemplateVM creation), just
  `qvm-tags <template> add hexagon`.

Rename either tag with `--admin-tag` / `--target-tag`. The one exception to the
pure-tag model is the `qubes_proxy` `disp-mgmt-*` disposables: the
`ansible.CreateManagementPolicies` RPC hard-checks `created-by-<calling-qube>`
on them, so their lifecycle grants are keyed on `@tag:created-by-<admin>` — one
block per `--admin-qube` (default: the local host). The unmanaged sys-VMs the
`qube` module reads for netvm checks stay explicit (`--sys-vm`, repeatable);
`--mgmt-dispvm` overrides a non-default management DispVM. Provisioning (qube
lifecycle) stays with hexagon's other verbs; Ansible only enforces config
*inside* qubes. The policy also carries the two plain qrexec grants hexagon's
own verbs need from that MgmtVM: `qubes.VMShell` (`hexagon reboot` powers a
netvm off from inside when clients are attached) and
`qubes.StartApp +qubes-run-terminal` (`hexagon terminal` and `reboot -t`).

## Installation
In order to use the tool, you must build the RPM in an AppVM,
then copy that RPM package into dom0.
**Copying code to dom0 is dangerous.** Make sure you've read
the [Qubes OS documentation on copying-to-dom0](https://www.qubes-os.org/doc/copy-from-dom0/#copying-to-dom0)
before proceeding.

Build the RPM in the AppVM where you checked out this repo:

```
just rpm
```

This produces a single universal `noarch` RPM (pure Python source plus a
launcher; runtime deps come from dom0), so the same package installs on any
Qubes/Fedora version. Copy it to dom0:

```
qvm-run --pass-io work '/home/user/hexagon/rpm-build/RPMS/noarch/hexagon-0.2.0-1.noarch.rpm' > /tmp/hexagon.rpm
sudo dnf install -y /tmp/hexagon.rpm
```

`just install` does the same in place, wherever the checkout is: in dom0 (after
`just clone`), or in the AppVM that built it, to drive hexagon over the Admin
API from there. In a template-based AppVM that lasts until its next restart.

To uninstall, simply run `sudo dnf remove hexagon` in dom0.

## Examples

### Updating templates

When a new version of fedora is released, you must manually update
your templates to the new version.

```
[user@dom0 ~]$ hexagon ls --template fedora-34
2020-05-29 16:38:04 DEBUG    main() Listing VMs...
default-mgmt-dvm
fedora-34-dvm
sys-firewall
sys-net
sys-usb
```

Great! Looks like we have the `sys-*` VMs already taken care of.
But what about some of the default domains?

```
[user@dom0 ~]$ hexagon ls --template fedora-29
2020-05-29 16:38:16 DEBUG    main() Listing VMs...
vault
work
```

Yikes! The `vault` and `work` VMs are several versions behind.
Let's update them to the latest:

```
[user@dom0 ~]$ hexagon reconcile work vault --template fedora-34
2020-05-29 16:38:30 DEBUG    main() Performing reconcile of VMs: ['work', 'vault']
2020-05-29 16:38:30 DEBUG    reconcile() <HexagonQube: vault> requires changes: [<VMConfigChange:template: fedora-29 -> fedora-34, reboot=True>]
2020-05-29 16:38:30 DEBUG    reconcile() <HexagonQube: work> requires changes: [<VMConfigChange:template: fedora-29 -> fedora-34, reboot=True>]
2020-05-29 16:38:31 DEBUG    main() VM operation reconcile completed: work
2020-05-29 16:38:31 DEBUG    main() VM operation reconcile completed: vault
2020-05-29 16:38:31 DEBUG    main() All VM reconcile operations finished, with 0 errors
[user@dom0 ~]$ hexagon ls --template fedora-34
2020-05-29 16:38:34 DEBUG    main() Listing VMs...
default-mgmt-dvm
fedora-34-dvm
sys-firewall
sys-net
sys-usb
vault
work
```

The `vault` and `work` VMs are now based on the latest version of Fedora.
Much better!

## Development

To clone the repository into dom0 (dangerous!):

```
qvm-run --pass-io work "tar -c --exclude-vcs -C '/home/user/src/hexagon' ." > /tmp/hexagon.tar
mkdir -p ~/hexagon
tar -xf /tmp/hexagon.tar -C ~/hexagon --strip-components=1
```

From then on, from dom0, you can:

```
cd ~/hexagon
just clone
```

Note that you may need to set `HEXAGON_DEV_VM` and `HEXAGON_DEV_DIR` as env vars,
depending on your setup.

## Reproducible builds
The RPM is built by a Nix derivation (`nix build .#rpm`, which is what `just rpm`
invokes), so the output is byte-for-byte reproducible by construction: the same
source revision always yields an identical `noarch` RPM. Verify by building twice
and comparing checksums:

```
just rpm && sha256sum rpm-build/RPMS/noarch/*.rpm
just rpm && sha256sum rpm-build/RPMS/noarch/*.rpm
```

A single universal `noarch` RPM is produced, suitable for every supported Qubes
version.

## Testing and verification

When making changes, ensure all the following pass:

```
just lint
just test
just build
```

Make sure to activate the nix devshell, as appropriate.

## License

GPLv2 (`GPL-2.0-only`), same as other Qubes tools. See [`LICENSE`](LICENSE).
