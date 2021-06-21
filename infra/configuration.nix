let
  system = "x86_64-linux";

  flake = (import (fetchTarball https://github.com/edolstra/flake-compat/archive/master.tar.gz) {
    src = ../.;
  }).defaultNix;

  nixpkgs = flake.inputs.nixpkgs;
in
import "${nixpkgs}/nixos" {
  inherit system;
  configuration = {
    imports = [ ./concrexit.nix ];
    nixpkgs.overlays = [ flake.overlay."${system}" ];
  };
}
