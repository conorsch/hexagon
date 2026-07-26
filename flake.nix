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

        # The version is declared in pyproject.toml (read here for the RPM
        # derivation's name/metadata) and mirrored in the spec's %global version.
        # `just bump <version>` keeps the two in sync; see docs/releasing.md.
        version = (builtins.fromTOML (builtins.readFile ./pyproject.toml)).project.version;

        # Python environment for tests and building the RPM. Linting/formatting is
        # handled by the standalone `ruff` in `tooling`, not via this env. The dom0
        # RPM ships pure source (no compiled deps), so pip + setuptools are all
        # that's required at build time.
        pythonEnv = pkgs.python313.withPackages (ps: with ps; [
          build
          jinja2 # `hexagon policy` renders its template with jinja2 (present in dom0 via Ansible)
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

        # Build the dom0 RPM reproducibly: create the sdist tarball, hand it to
        # rpmbuild, and emit the single noarch RPM. This is the canonical build;
        # `just rpm` simply invokes it.
        packages.rpm = pkgs.stdenv.mkDerivation {
          pname = "hexagon-rpm";
          inherit version;

          src = ./.;

          nativeBuildInputs = [ pythonEnv pkgs.rpm ];

          dontConfigure = true;

          # Reproducible build timestamp. A flake build doesn't include .git in
          # the sandbox, so use self.lastModified as the revision-tracking
          # equivalent of the latest commit's epoch.
          SOURCE_DATE_EPOCH = toString (self.lastModified or 315532800);

          buildPhase = ''
            runHook preBuild

            export HOME="$TMPDIR"

            # The unpacked source lives in the read-only Nix store, so give
            # rpmbuild a writable _topdir under $TMPDIR to create BUILD/ etc.
            topdir="$TMPDIR/rpm-build"
            mkdir -p dist "$topdir"/{SOURCES,SPECS,BUILD,RPMS,tmp}

            # Bake the version string into a generated module so the runtime
            # can read it without dist-info (the noarch RPM ships bare .py).
            # The build runs in an isolated Nix store path, so this does not
            # pollute the user's checkout.
            echo "VERSION = \"${version}\"" > hexagon/_version.py

            # PEP 517 sdist; --no-isolation uses the env's setuptools (offline).
            python3 -m build --sdist --no-isolation

            # PEP 440 normalizes versions (e.g. 0.2.1-alpha.0 → 0.2.1a0).  RPM
            # rejects dashes in Version:, so derive the rpm-safe version from the
            # actual tarball name rather than the raw pyproject.toml string.
            sdist=$(ls -1 dist/*.tar.gz | head -n1)
            rpm_version=$(basename "$sdist" .tar.gz | sed 's/^hexagon-//')
            cp "$sdist" "$topdir/SOURCES/"
            cp rpm-build/SPECS/hexagon.spec "$topdir/SPECS/"

            rpmbuild \
              --nodeps \
              --define "_topdir $topdir" \
              --define "_tmppath $topdir/tmp" \
              --define "_prefix /usr" \
              --define "version $rpm_version" \
              -bb --clean "$topdir/SPECS/hexagon.spec"

            runHook postBuild
          '';

          installPhase = ''
            runHook preInstall
            mkdir -p "$out"
            cp "$TMPDIR/rpm-build"/RPMS/noarch/*.rpm "$out/"
            runHook postInstall
          '';

          meta = {
            description = "Hexagon CLI RPM(s) for Qubes OS dom0";
            license = pkgs.lib.licenses.gpl2Only;
          };
        };

        # Nix package installable via `nix profile install .#hexagon` or
        # `nix run .#hexagon`. Uses buildPythonApplication so [project.scripts]
        # in pyproject.toml generates both `hexagon` and `qvm-reboot` console
        # entry points on PATH automatically.
        #
        # qubesadmin is NOT declared as a dependency here because it is not in
        # nixpkgs. It is available on Qubes OS via RPM (python3-qubesadmin in
        # dom0, or dnf install qubes-core-admin-client in an AppVM). The
        # package builds fine but hexagon will exit with a clear error at
        # runtime if qubesadmin is not on PYTHONPATH.
        packages.hexagon = pkgs.python313.pkgs.buildPythonApplication {
          pname = "hexagon";
          inherit version;
          pyproject = true;

          src = ./.;

          nativeBuildInputs = [
            pkgs.python313.pkgs.build
            pkgs.python313.pkgs.setuptools
          ];

          propagatedBuildInputs = [
            pkgs.python313.pkgs.jinja2 # `hexagon policy` renders its template
            pkgs.python313.pkgs.pyyaml
          ];

          # Bake the version string for runtime introspection (same as the RPM
          # build does in its buildPhase).
          preConfigure = ''
            echo "VERSION = \"${version}\"" > hexagon/_version.py
          '';

          # Tests need a live Qubes Admin API; run them via `just test`.
          doCheck = false;

          meta = with pkgs.lib; {
            description = "Alternative CLI for managing Qubes OS VMs";
            license = licenses.gpl2Only;
            mainProgram = "hexagon";
            homepage = "https://github.com/conorsch/hexagon";
          };
        };

        # Standalone CLI package that symlinks both entry-point binaries into
        # a single installable unit.  This is the default because it clearly
        # signals "this gives you `hexagon` and `qvm-reboot` on PATH".
        packages.hexagon-cli = pkgs.runCommand "hexagon-cli"
          {
            meta = with pkgs.lib; {
              description = "Hexagon CLI tools (hexagon + qvm-reboot)";
              license = licenses.gpl2Only;
              mainProgram = "hexagon";
            };
          }
          ''
            mkdir -p $out/bin
            ln -s ${self.packages.${system}.hexagon}/bin/hexagon $out/bin/hexagon
            ln -s ${self.packages.${system}.hexagon}/bin/qvm-reboot $out/bin/qvm-reboot
          '';

        # Make the combined CLI package the default
        packages.default = self.packages.${system}.hexagon-cli;

        # Make the containerised toolchest available as an explicit target,
        # but no longer the default.
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

        # Expose both CLIs as flake apps so `nix run .#hexagon` and
        # `nix run .#qvm-reboot` work without a profile install.
        apps.hexagon = {
          type = "app";
          program = "${self.packages.${system}.hexagon-cli}/bin/hexagon";
        };
        apps.qvm-reboot = {
          type = "app";
          program = "${self.packages.${system}.hexagon-cli}/bin/qvm-reboot";
        };
      });
}
