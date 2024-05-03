# shell.nix
#=========================================================================#
#
# To create shell environment and install packages run in project directory
# where this file is located:
#
#   $ nix-shell
#
#=========================================================================#
let
  pkgs = import <nixpkgs> {};
in
  pkgs.mkShell {
    packages = [
      (pkgs.python3.withPackages (py: [
        # select Python packages here

        # [dependencies]
        py.pygame
        # py.noise

        py.numpy

        # [dev_dependencies]
        py.line_profiler
        py.memory_profiler
        # python-pkgs.pandas
        # python-pkgs.requests
      ]))
    ];
  }
