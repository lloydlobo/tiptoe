# file: shell-example.nix
#=========================================================================#
#
# To create shell environment and install packages run in project directory
# where this file is located:
#
#   $ nix-shell
#   $ nix-shell --show-trace
#
#=========================================================================#
let
  pkgs = import <nixpkgs> {};

  python-with-packages = pkgs.python3.withPackages (ps:
    with ps; [
      # public
      pygame

      # internal
      hypothesis
      line_profiler
      memory_profiler
      pip
      pytest
    ]);

  altgraph = pkgs.python3Packages.buildPythonPackage rec {
    pname = "altgraph";
    version = "0.17.3"; # You can update to the latest version
    src = pkgs.python3Packages.fetchPypi {
      inherit pname version;
      sha256 = "rTM1gRTffJQWzbj6HqpYUhZsUFEYcXAhxqjHx6u9A90=";
    };
    doCheck = false;
  };

  pyinstaller = pkgs.python3Packages.buildPythonPackage rec {
    pname = "pyinstaller";
    version = "5.13.2"; # You can update to the latest version
    src = pkgs.python3Packages.fetchPypi {
      inherit pname version;
      sha256 = "yOXTSJw6fMX4QBwtH0inDliPmWfjkcOwbdrB9oX41dI=";
    };
    doCheck = false;
    propagatedBuildInputs = with pkgs.python3Packages; [
      setuptools

      # NOTE: If `altgraph` not available in your current nixpkgs, we need to
      # define it separately, similar to pyinstaller above.
      altgraph
    ];
    buildInputs = [
      pkgs.zlib
    ];
    preBuild = ''
      export PYI_STATIC_ZLIB=1
    '';
  };
in
  pkgs.mkShell {
    packages = [
      python-with-packages
      pyinstaller
    ];
    shellHook = ''
      echo "Python environment ready with PyInstaller"
      python --version
      pyinstaller --version
    '';
  }
