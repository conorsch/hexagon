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

            # PEP 517 sdist; --no-isolation uses the env's setuptools (offline).
            python3 -m build --sdist --no-isolation
            cp dist/*.tar.gz "$topdir/SOURCES/"
            cp rpm-build/SPECS/hexagon.spec "$topdir/SPECS/"

            # The spec ships pure source + a launcher (no pip, no site-packages),
            # so one noarch RPM covers every dom0. Nothing here is Fedora- or
            # Python-version-specific, hence no substituteInPlace or build loop.
            rpmbuild \
              --nodeps \
              --define "_topdir $topdir" \
              --define "_tmppath $topdir/tmp" \
              --define "_prefix /usr" \
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
