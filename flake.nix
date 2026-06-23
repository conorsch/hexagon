{
  description = "Dev shell for building Hexagon RPM for QubesOS";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
    flake-utils.url = "github:numtide/flake-utils";
    flake-utils.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          system = "x86_64-linux";
        };

        # Python environment for tests and building the RPM. Linting/formatting is
        # handled by the standalone `ruff` in `tooling`, not via this env. The dom0
        # RPM ships pure source (no compiled deps), so pip + setuptools are all
        # that's required at build time.
        pythonEnv = pkgs.python313.withPackages (ps: with ps; [
          pip
          pytest
          pytest-testinfra
          pytest-xdist
          setuptools
        ]);

        # Defining package list outside of devshell, so it can be used in devshell & container image.
        tooling = with pkgs; [
          ansible
          ansible-lint
          bashInteractive
          cargo-nextest
          coreutils
          diffoscope
          fd
          file
          git
          glibcLocales
          go
          gum
          gzip
          gnutar
          hcloud
          jq
          just
          ntfy-sh
          perl
          pythonEnv
          rpm
          rsync
          ruff
          shellcheck
          sops
          xz
          yamllint
          yq
        ];

      in
      {
        devShells.default = pkgs.mkShell {
          name = "ruin.dev infra";
          # nativeBuildInputs = [ pkgs.bashInteractive ];
          buildInputs = tooling;

        };

        # Build the dom0 RPM(s) reproducibly. Mirrors scripts/build-dom0-rpm:
        # create the sdist tarball, hand it to rpmbuild, and emit the noarch RPMs.
        packages.rpm = pkgs.stdenv.mkDerivation {
          pname = "hexagon-rpm";
          version = "0.1.4";

          src = ./.;

          nativeBuildInputs = [ pythonEnv pkgs.rpm ];

          dontConfigure = true;

          # Reproducible build timestamp. scripts/build-dom0-rpm derives this from
          # the latest git commit, but a flake build doesn't include .git in the
          # sandbox; self.lastModified is the revision-tracking equivalent.
          SOURCE_DATE_EPOCH = toString (self.lastModified or 315532800);

          buildPhase = ''
            runHook preBuild

            export HOME="$TMPDIR"
            pyExe="$(command -v python3)"
            hostPyVer="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"

            # The spec hardcodes Fedora's /usr/bin/python3, which is absent in the
            # Nix sandbox; point it at the python from nativeBuildInputs instead.
            substituteInPlace rpm-build/SPECS/hexagon.spec \
              --replace-fail '/usr/bin/python3' "$pyExe"

            # Fedora's python installs under the /usr prefix; the Nix python uses
            # its own store prefix, which would make the spec's sitelib relocation
            # miss. Pin pip's install prefix to /usr (a no-op on Fedora) so the
            # buildroot layout matches what the spec expects.
            substituteInPlace rpm-build/SPECS/hexagon.spec \
              --replace-fail '--no-build-isolation --root %{buildroot} .' \
                             '--no-build-isolation --prefix /usr --root %{buildroot} .'

            # pip stamps the installed script with the build-time interpreter,
            # which under Nix is a /nix/store path that won't exist in dom0.
            # Rewrite it to the Fedora interpreter the package targets.
            substituteInPlace rpm-build/SPECS/hexagon.spec \
              --replace-fail \
                'find %{buildroot} -exec touch -m -d @%{_source_date_epoch} {} +' \
                'sed -i "1s|^#!.*python3.*|#!/usr/bin/python3|" %{buildroot}/%{_bindir}/%{srcname}
            find %{buildroot} -exec touch -m -d @%{_source_date_epoch} {} +'

            mkdir -p dist rpm-build/SOURCES rpm-build/RPMS
            python3 setup.py sdist
            cp dist/*.tar.gz rpm-build/SOURCES/

            # See scripts/build-dom0-rpm for the Qubes->Fedora->Python version matrix.
            #   Qubes 4.2.x => F37 => python3.11
            #   Qubes 4.3.x => F42 => python3.13
            for i in 37 42; do
              python_version="3.11"
              if [ "$i" = 42 ]; then
                python_version="3.13"
              fi
              echo "Building for dom0 based on .fc''${i} with Python ''${python_version}..."
              rpmbuild \
                --nodeps \
                --define "_topdir $PWD/rpm-build" \
                --define "_prefix /usr" \
                --define "dist .fc''${i}" \
                --define "_target_python_version $python_version" \
                --define "python3_version $hostPyVer" \
                -bb --clean rpm-build/SPECS/hexagon.spec
            done

            runHook postBuild
          '';

          installPhase = ''
            runHook preInstall
            mkdir -p "$out"
            cp rpm-build/RPMS/noarch/*.rpm "$out/"
            runHook postInstall
          '';

          meta = {
            description = "Hexagon CLI RPM(s) for Qubes OS dom0";
            license = pkgs.lib.licenses.gpl3Plus;
          };
        };

        # Add container output
        packages.container = pkgs.dockerTools.buildImage {
          name = "hexagon";
          tag = "latest";

          # Configure container contents
          copyToRoot = tooling;

          # Optional: Configure container metadata
          config = {
            Cmd = [ "${pkgs.bashInteractive}/bin/bash" ];
            WorkingDir = "/";
            # Env = [
            #   "PATH=/bin"
            #   "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
            # ];
          };
        };

        # Make the container the default package
        packages.default = self.packages.${system}.container;
      });
}
