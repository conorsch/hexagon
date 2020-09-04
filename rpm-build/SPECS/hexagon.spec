%global srcname hexagon
%global version 0.1.0

Name:		%{srcname}
Version:	%{version}
Release:	1%{?dist}
Summary:	Alternative CLI for managing Qubes OS VMs

Group:		Library
License:	GPLv3+
URL:		https://github.com/conorsch/hexagon
Source0:	%{srcname}-%{version}.tar.gz

BuildArch:      noarch
#BuildRequires:	python3-setuptools
#BuildRequires:	python3-devel

# This package installs all standard VMs in Qubes
Requires:       python3-qubesadmin, qubes-core-admin-client

%description

This package contains a Python3 library and "hexagon" CLI
program to aid in managing QubesOS VMs.

# Don't build .pyc files
%undefine py_auto_byte_compile

%prep
%setup -n %{srcname}-%{version}

%build
%{__python3} setup.py build

%install
%{__python3} setup.py install --no-compile --skip-build --root %{buildroot}
#install -m 755 -d %{python3_sitelib}/hexagon

%files
%doc README.md
%{python3_sitelib}/hexagon/*
hexagon/*

%post
echo "DEBUG: finished installing hexagon rpm"

%changelog
* Tue Jul 07 2020 SecureDrop Team <securedrop@freedom.press> - 0.4.0
- Consolidates updates from two stages into one
- Makes the updater UI more compact

* Tue Jun 16 2020 SecureDrop Team <securedrop@freedom.press> - 0.3.1
- Updates SecureDrop Release Signing public key with new expiry

* Thu May 28 2020 SecureDrop Team <securedrop@freedom.press> - 0.3.0
- Upgrades sys-net, sys-firewall and sys-usb to Fedora31 TemplateVMs
- Removes package updates from sd-log AppVM config
- Permit whitelisting VMs for copy/paste & copying logs via tags
- Safely shut down sys-usb; tweak logging
- Clear Salt cache and synchronize Salt before installing/uninstalling
- Logs more VM state info in updater

* Mon Mar 30 2020 SecureDrop Team <securedrop@freedom.press> - 0.2.4
- Adjusts VM reboot order, to stabilize updater behavior

* Wed Mar 11 2020 SecureDrop Team <securedrop@freedom.press> - 0.2.3
- Aggregate logs for both TemplateVMs and AppVMs
- Add securedrop-admin --uninstall
- Optimize Fedora Template updates
- Convert sd-proxy to SDW base template

* Tue Mar 03 2020 SecureDrop Team <securedrop@freedom.press> - 0.2.2
- Start preflight updater on boot
- Poweroff workstation on lid close
- Default mimetype handling
- Disable log forwarding in sd-log

* Tue Feb 25 2020 SecureDrop Team <securedrop@freedom.press> - 0.2.1
- Fixes logging and launcher configuration due to omitted file in manifest

* Mon Feb 24 2020 SecureDrop Team <securedrop@freedom.press> - 0.2.0
- Update version to 0.2.0 in preparation for beta release
- Includes log forwarding from AppVMs to sd-log

* Tue Feb 18 2020 SecureDrop Team <securedrop@freedom.press> - 0.1.5
- Removes legacy cron job updater, replaced by preflight udpater

* Fri Feb 14 2020 SecureDrop Team <securedrop@freedom.press> - 0.1.4
- Modifies updater to allow for a configurable interval between checks

* Tue Feb 11 2020 SecureDrop Team <securedrop@freedom.press> - 0.1.3
- Adds sdw-notify script
- Sets executable bits within package specification
- Disable build root policy for bytecode generation in package spec

* Mon Feb 03 2020 Mickael E. <mickae@freedom.press> - 0.1.2
- Provides dev/staging/prod split logic.

* Fri Jan 10 2020 redshiftzero <jen@freedom.press> - 0.1.1
- First alpha release.

* Fri Oct 26 2018 Kushal Das <kushal@freedom.press> - 0.0.1-1
- First release
