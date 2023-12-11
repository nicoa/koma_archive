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

      sharedOverlays = [ inputs.poetry2nix.overlays.default ];

      outputsBuilder = channels: {
        packages = let
          package = channels.nixpkgs.poetry2nix.mkPoetryApplication {
            projectDir = ./.;
          };
        in {
          default = package;
          koma_archive = package;
        };

        devShells.default = let
          poetryEnv =
            channels.nixpkgs.poetry2nix.mkPoetryEnv { projectDir = ./.; };
        in poetryEnv.env.overrideAttrs (oldAttrs: {
          buildInputs = [ channels.nixpkgs.poetry channels.nixpkgs.black ];
        });
      };
    };
}
