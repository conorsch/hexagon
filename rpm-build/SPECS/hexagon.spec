%global srcname hexagon
%global version 0.1.0
%global python3_version 3.5
%global python3_sitelib /usr/lib/python3.5/site-packages
%global __python3 /usr/bin/python3
%global dist .fc25
%global _buildhost hexagon

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

# Ensure that SOURCE_DATE_EPOCH is honored
%define use_source_date_epoch_as_buildtime 1

%prep
%setup -q

%install
%{__python3} setup.py install --install-lib %{python3_sitelib} --no-compile --root %{buildroot}
find %{buildroot} -type d -iname '*.egg-info' -print0 | xargs -0 -r rm -rf

%files
%{python3_sitelib}/hexagon/*.py

%post
echo "DEBUG: finished installing hexagon rpm"

%changelog
* Fri Nov 13 2020 Conor Schaefer <conor@freedom.press> - 0.1.0
- Simply trying to get a working RPM
