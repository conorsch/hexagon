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
```

## Installation
In order to use the tool, you must build the RPM in an AppVM,
then copy that RPM package into dom0.
**Copying code to dom0 is dangerous.** Make sure you've read
the [Qubes OS documentation on copying-to-dom0](https://www.qubes-os.org/doc/copy-from-dom0/#copying-to-dom0)
before proceeding.

Build the RPM in the AppVM where you checked out this repo:

```
make rpm
```

Then, copy the package to dom0:

```
qvm-run --pass-io work '/home/user/hexagon/rpm-build/RPMS/noarch/hexagon-0.1.2-1.fc32.noarch.rpm' > /tmp/hexagon.rpm
sudo dnf --disablerepo=qubes-dom0-cached install -y /tmp/hexagon.rpm
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

## Reproducible builds
The RPM build process is reproducible. You can use the `make reprotest` target to verify.
There's one odd assumption, which is that you're building in a Debian Stable AppVM.
It was simply easier to wire up the requisite logic under Debian than F32, but the build
process really should support Fedora properly. To build:

```
make install-deps
make rpm
make reprotest
```

Both Qubes 4.0 & 4.1-compatible RPM packages will be created. Install the one that's appropriate for your environment.
