%global srcname hexagon
%global version 0.1.4

# For reproducible builds
%global _buildhost hexagon
%global _source_date_epoch %{getenv:SOURCE_DATE_EPOCH}

%global python3 /usr/bin/python3
%define optflags -O2 -g

# Override the detected sitelib, so that a version for dom0 is used.
# Relies on build-time args passed in on CLI to rpm-build.
%global python3_sitelib /usr/lib/python%{_target_python_version}/site-packages

# Prevent rpm-build from adding an implicit dependency on Python ABI,
# that's tied to a specific Python version.
%undefine __python_requires

Name:		%{srcname}
Version:	%{version}
# The "dist" var is mandatory, and passed in at build time.
# We use it to force a specific Fedora version, suitable for dom0.
Release:	1%{?dist}
Summary:	Alternative CLI for managing Qubes OS VMs

Group:		Library
License:	GPLv3+
URL:		https://github.com/conorsch/hexagon
Source0:	%{srcname}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:	python%{_target_python_version}-devel
BuildRequires:	python3-pip

# This package installs all standard VMs in Qubes
Requires:   python3-qubesadmin, qubes-core-admin-client

%description

This package contains a Python3 library and "hexagon" CLI
program to aid in managing QubesOS VMs.

# Don't build .pyc files
%undefine py_auto_byte_compile

# Ensure that SOURCE_DATE_EPOCH is honored
%define use_source_date_epoch_as_buildtime 1

%prep
echo "The pythonversions i can see in prep are: "
echo "%{_target_python_version}"
%setup -q -n %{name}-%{version}

%install
%{python3} -m pip install --no-compile --no-index --no-build-isolation --root %{buildroot} .

%if "%{python3_version}" != "%{_target_python_version}"
# Move sitelib built by host Fedora's pip to match expectations for target Python version in dom0.
# This is safe because there are no pip dependencies, only raw source files for hexagon.
# We only do this if the target python version and the build host's python version don't match.
mv %{buildroot}/usr/lib/python%{python3_version} %{buildroot}/usr/lib/python%{_target_python_version}
%endif

# prune direct_url.json content, because it varies per-build, and breaks reproducibility.
rm %{buildroot}/%{python3_sitelib}/%{srcname}-%{version}.dist-info/direct_url.json
sed -i "/\.dist-info\/direct_url\.json,/d" %{buildroot}/%{python3_sitelib}/%{srcname}-%{version}.dist-info/RECORD
find %{buildroot} -exec touch -m -d @%{_source_date_epoch} {} +

%files
%{python3_sitelib}/%{srcname}/*.py
%{python3_sitelib}/*%{version}.dist-info/*
%{_bindir}/%{srcname}

%post
echo "DEBUG: finished installing hexagon rpm"

%changelog
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
