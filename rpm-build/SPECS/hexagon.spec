%global srcname hexagon

# hexagon is pure Python. Its runtime deps (qubesadmin & friends) already live
# in dom0, so there is nothing to compile or resolve at install time: we just
# drop the source into a fixed libdir and put a launcher on PATH. Because the
# payload is plain .py (never byte-compiled), it is Python-version-independent,
# so a single noarch RPM serves every dom0 (Qubes 4.2/py3.11, 4.3/py3.13, ...).
%global hexagon_libdir %{_prefix}/lib/%{srcname}

# Reproducible builds: pin the build host and honor SOURCE_DATE_EPOCH.
%global _buildhost hexagon
%global source_date_epoch %{getenv:SOURCE_DATE_EPOCH}
%define use_source_date_epoch_as_buildtime 1

# There are no compiled artifacts and no per-version site-packages, so suppress
# the implicit Python-ABI dependency and byte-compilation entirely.
%undefine __python_requires
%undefine py_auto_byte_compile

Name:		%{srcname}
Version:	%{version}
Release:	1
Summary:	Alternative CLI for managing Qubes OS VMs

Group:		Library
License:	GPL-2.0-only
URL:		https://github.com/conorsch/hexagon
Source0:	%{srcname}-%{version}.tar.gz

BuildArch:	noarch

# hexagon imports qubesadmin at runtime. The package that provides it varies
# across Qubes environments (python3-qubesadmin in templates, pre-installed
# under a different name in dom0 where qubes-core-admin-client is not a
# resolvable package), so use a soft dependency: dnf pulls it in when the
# package exists in the repos, but never blocks installation where it
# doesn't. hexagon will error clearly at runtime if the module is missing.
Recommends:	python3-qubesadmin
# `hexagon policy` renders its template with Jinja2. dom0 already has it (Ansible
# and qubesadmin both pull it in), so a soft dep suffices: installed where the
# package exists, never blocking where hexagon's other verbs are all that's used.
Recommends:	python3-jinja2

%description
This package contains a Python3 library and "hexagon" CLI
program to aid in managing QubesOS VMs.

%prep
%setup -q -n %{name}-%{version}

%install
# Ship the package source verbatim into a version-independent libdir...
install -d -m 0755 %{buildroot}%{hexagon_libdir}/%{srcname}
install -m 0644 %{srcname}/*.py %{buildroot}%{hexagon_libdir}/%{srcname}/

# ...and launchers on PATH that run it against dom0's system Python.
install -d -m 0755 %{buildroot}%{_bindir}

cat > %{buildroot}%{_bindir}/%{srcname} <<EOF
#!/usr/bin/python3
import sys

sys.path.insert(0, "%{hexagon_libdir}")
from hexagon.cli import main

main()
EOF
chmod 0755 %{buildroot}%{_bindir}/%{srcname}

# qvm-reboot is a thin wrapper that execs "hexagon reboot" for qvm-* parity.
cat > %{buildroot}%{_bindir}/qvm-reboot <<EOF
#!/usr/bin/python3
import sys

sys.path.insert(0, "%{hexagon_libdir}")
from hexagon.cli import qvm_reboot_main

qvm_reboot_main()
EOF
chmod 0755 %{buildroot}%{_bindir}/qvm-reboot

# Normalize mtimes for reproducibility.
find %{buildroot} -exec touch -m -d @%{source_date_epoch} {} +

%files
%{hexagon_libdir}/%{srcname}/*.py
%{_bindir}/%{srcname}
%{_bindir}/qvm-reboot

%changelog
* Mon Jul 21 2026 Conor Schaefer <conor@ruin.dev> - 0.3.0
- Default --mgmtvm to running machine's hostname (socket.gethostname())
- Add hexagon policy subcommand — renders dom0 qrexec policy for ManagementVM
- Resolve qubesadmin at install time; softens qubes-core-admin-client dep
- Add packages.hexagon flake output for nix profile install

* Mon Jul 20 2026 Conor Schaefer <conor@ruin.dev> - 0.2.1-alpha.2
- Drop hard Requires on qubes-core-admin-client (not available in dom0)
- Soften python3-qubesadmin to Recommends so the same RPM installs in both
  dom0 and AppVMs

* Sun Jul 19 2026 Conor Schaefer <conor@ruin.dev> - 0.2.1-alpha.1
- Install qvm-reboot launcher alongside hexagon
- Bake version string into _version.py so --version works without dist-info

* Thu Jul 2 2026 Conor Schaefer <conor@ruin.dev> - 0.1.4
- Build a single universal noarch RPM (no pip, no per-Fedora variants)
- Install source to /usr/lib/hexagon with a thin /usr/bin/hexagon launcher

* Tue Dec 9 2025 Conor Schaefer <conor@ruin.dev> - 0.1.4
- Update docs and defaults for Qubes 4.2
- Move script back /usr/bin/local/hexagon -> /usr/bin/hexagon

* Fri Feb 11 2022 Conor Schaefer <conor@freedom.press> - 0.1.3
- Update docs and defaults for Qubes 4.1
- Move script back /usr/bin/hexagon -> /usr/local/bin/hexagon

* Mon Nov 29 2021 Conor Schaefer <conor@freedom.press> - 0.1.2
- Fix reconcile action for template migrations
- Support shutdown for DispVMs (destroys them)
- Move script /usr/local/bin/hexagon -> /usr/bin/hexagon
- Add --version flag

* Fri Mar 12 2021 Conor Schaefer <conor@freedom.press> - 0.1.1
- Builds RPM, reproducibly, for Qubes 4.0 & 4.1
- Adds CI tests to verify reproducible builds via reprotest

* Fri Nov 13 2020 Conor Schaefer <conor@freedom.press> - 0.1.0
- Simply trying to get a working RPM
