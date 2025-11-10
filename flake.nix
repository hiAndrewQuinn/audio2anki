{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }: let
    systems = [ "x86_64-linux" "aarch64-linux" ];
    lib = nixpkgs.lib;
  in {
    packages = lib.genAttrs systems (system: let
      pkgs = nixpkgs.legacyPackages.${system};
      pythonPackages = with pkgs.python3Packages; [
        cached-property
        chevron
        click
        python-dotenv
        frozendict
        genanki
        librosa
        pydub
        pyyaml
        tqdm
      ];
    in {
      default = pkgs.python3Packages.buildPythonApplication {
        pname = "audio2anki";
        version = "0.1.0";
        src = ./.;
        pyproject = true;
        build-system = [ pkgs.python3Packages.setuptools ];
        propagatedBuildInputs = pythonPackages;
        buildInputs = [ pkgs.ffmpeg-full pkgs.yt-dlp ];
      };
    });

    devShells = lib.genAttrs systems (system: let
      pkgs = nixpkgs.legacyPackages.${system};
      pythonPackages = with pkgs.python3Packages; [
        cached-property
        chevron
        click
        python-dotenv
        frozendict
        genanki
        librosa
        pydub
        pyyaml
        tqdm
      ];
    in {
      default = pkgs.mkShell {
        packages = [
          (pkgs.python3.withPackages (ps: pythonPackages))
        ];
      };
    });
  };
}