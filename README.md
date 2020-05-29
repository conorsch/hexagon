# hexagon
A rough-and-tumble CLI tool for managing [Qubes OS](https://qubes-os.org) VMs.

## Why?
The existing `qvm-*` tooling provided by upstream Qubes is stable and concise,
but lacks a few convenient operations such as "reboot", or "update all packages".
Hexagon aims to provide convenient CLI actions for those edge cases.

More importantly, hexagon is meant to facilicate experimenting with VM management.
As such, it makes no promises about stability or maintenance: use at your own risk.

## Usage


```
# List all VMs with known available package updates
hexagon ls --updatable

# List all VMs with recently updated templates
hexagon ls --outdated

# Reboot particular VM
hexagon reboot sys-whonix

# Modify TemplateVM settings for several VMs at once (e.g. fedora-30 -> fedora-31)
hexagon reconcile --template fedora-31 sys-usb sys-net sys-firewall

# Upgrade packages within a particular VM
hexagon update fedora-31

# Upgrade packages for all VMs with pending updates
hexagon update
```


## Installation
In order to use the tool, you must copy the code into dom0.
**Copying code to dom0 is dangerous.** Make sure you've read
the [Qubes OS documentation on copying-to-dom0](https://www.qubes-os.org/doc/copy-from-dom0/#copying-to-dom0)
before proceeding.


Cloning for the first time:
```
qvm-run --pass-io work 'tar -c -C /home/user/ hexagon' | tar xvf -
cd hexagon
make install
```

Thereafter you can use:

```
make clone
make install
```

TODO: make uninstall target.

## Examples

### Updating templates

When a new version of fedora is released, you must manually update
your templates to the new version.

```
[user@dom0 ~]$ hexagon ls --template fedora-31
2020-05-29 16:38:04 DEBUG    main() Listing VMs...
default-mgmt-dvm
fedora-31-dvm
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
[user@dom0 ~]$ hexagon reconcile work vault --template fedora-31
2020-05-29 16:38:30 DEBUG    main() Performing reconcile of VMs: ['work', 'vault']
2020-05-29 16:38:30 DEBUG    reconcile() <HexagonQube: vault> requires changes: [<VMConfigChange:template: fedora-29 -> fedora-31, reboot=True>]
2020-05-29 16:38:30 DEBUG    reconcile() <HexagonQube: work> requires changes: [<VMConfigChange:template: fedora-29 -> fedora-31, reboot=True>]
2020-05-29 16:38:31 DEBUG    main() VM operation reconcile completed: work
2020-05-29 16:38:31 DEBUG    main() VM operation reconcile completed: vault
2020-05-29 16:38:31 DEBUG    main() All VM reconcile operations finished, with 0 errors
[user@dom0 ~]$ hexagon ls --template fedora-31
2020-05-29 16:38:34 DEBUG    main() Listing VMs...
default-mgmt-dvm
fedora-31-dvm
sys-firewall
sys-net
sys-usb
vault
work
```

The `vault` and `work` VMs are now based on the latest version of Fedora.
Much better!
