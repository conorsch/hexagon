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

# Modify TemplateVM settings for several VMs at once (e.g. fedora-30 -> fedora-34)
hexagon reconcile --template fedora-34 sys-usb sys-net sys-firewall

# Upgrade packages within a particular VM
hexagon update fedora-34

# Upgrade packages for all VMs with pending updates
hexagon update

# Print the dom0 qrexec policy for a Qubes 4.3 Ansible ManagementVM
hexagon policy --mgmtvm fleet
```

### Ansible ManagementVM policy

`hexagon policy` renders the dom0 qrexec policy that lets a management qube
drive [Qubes 4.3 Ansible](https://github.com/QubesOS/qubes-ansible) (the
`qubesos.core` / `qubesos.security` collections). It's pure text generation —
no Admin API — so it runs in any AppVM; review the output, then apply it in
dom0:

```
qvm-run -p fleet 'hexagon policy --mgmtvm fleet' \
  | sudo tee /etc/qubes/policy.d/30-mgmtvm.policy
qubes-policy-lint /etc/qubes/policy.d/30-mgmtvm.policy
```

Every grant is sourced from the named MgmtVM; full management is scoped to
qubes tagged `created-by-<mgmtvm>`. Override the base templates and sys-VMs to
match your install with repeatable `--template` / `--sys-vm` flags (and
`--mgmt-dispvm` for a non-default management DispVM). Provisioning (qube
lifecycle) stays with hexagon's other verbs; Ansible only enforces config
*inside* qubes.

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

## License

GPLv2 (`GPL-2.0-only`), same as other Qubes tools. See [`LICENSE`](LICENSE).
