{
  description = "Generic stdio LSP for Unicode input completion";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { nixpkgs, ... }:
    let
      systems = [ "aarch64-darwin" "aarch64-linux" "x86_64-linux" ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in {
      packages = forAllSystems (pkgs: {
        default = pkgs.callPackage ./package.nix { };
        unicode-input-lsp = pkgs.callPackage ./package.nix { };
      });
      apps = forAllSystems (pkgs: {
        default = {
          type = "app";
          program = "${pkgs.callPackage ./package.nix { }}/bin/unicode-input-lsp";
        };
      });
      checks = forAllSystems (pkgs: {
        unicode-input-lsp = pkgs.callPackage ./package.nix { };
      });
      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShell { packages = [ (pkgs.callPackage ./package.nix { }) pkgs.python3 ]; };
      });
    };
}
