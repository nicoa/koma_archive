{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-23.11";
    utils.url = "github:gytis-ivaskevicius/flake-utils-plus";
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
      inputs = {
        nixpkgs.follows = "nixpkgs";
        flake-utils.follows = "utils/flake-utils";
      };
    };
  };

  outputs = { self, nixpkgs, utils, ... }@inputs:
    utils.lib.mkFlake {
      inherit self inputs;

      sharedOverlays =
        [ inputs.poetry2nix.overlays.default self.overlays.default ];

      overlays = rec {
        poetry2nix = inputs.poetry2nix.overlays.default;
        koma-archive = (final: prev: {
          koma-archive =
            final.poetry2nix.mkPoetryApplication { projectDir = ./.; };
        });

        default = koma-archive;
      };

      outputsBuilder = channels: {

        packages =
          let exports = utils.lib.exportPackages self.overlays channels;
          in exports // { default = exports.koma-archive; };

        devShells.default = let
          poetryEnv =
            channels.nixpkgs.poetry2nix.mkPoetryEnv { projectDir = ./.; };
        in poetryEnv.env.overrideAttrs (oldAttrs: {
          buildInputs = [ channels.nixpkgs.poetry channels.nixpkgs.black ];
        });
      };
    };
}
