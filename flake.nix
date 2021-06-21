{
  description = "Concrexit";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs";
  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.poetry2nix.url = "github:nix-community/poetry2nix";

  outputs = { self, nixpkgs, flake-utils, poetry2nix }:
    let
      supportedSystems = [ "x86_64-linux" "x86_64-darwin" ];
      version = self.shortRev or null;
    in
    flake-utils.lib.eachSystem supportedSystems (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          overlays = [
            (final: prev: {
              concrexit = self.packages.concrexit;
            })
            poetry2nix.overlay
          ];
        };
      in
      rec {
        packages = (flake-utils.lib.flattenTree {
          concrexit = pkgs.callPackage ./default.nix { inherit version; };
        });

        overlay = final: prev: {
          concrexit = packages.concrexit;
        };

        defaultPackage = packages.concrexit;

      });
}
