{ stdenvNoCC, python3, makeWrapper, lib }:
stdenvNoCC.mkDerivation {
  pname = "unicode-input-lsp";
  version = "1.0.0";
  src = ./.;
  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;
  doCheck = true;
  checkPhase = ''
    runHook preCheck
    PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}" ${python3}/bin/python3 -m unittest discover -s tests -v
    runHook postCheck
  '';
  installPhase = ''
    runHook preInstall
    mkdir -p "$out/share/unicode-input-lsp" "$out/bin"
    cp -r src/unicode_input_lsp "$out/share/unicode-input-lsp/"
    install -Dm644 LICENSE "$out/share/licenses/unicode-input-lsp/LICENSE"
    makeWrapper ${python3}/bin/python3 "$out/bin/unicode-input-lsp" \
      --add-flags "-m unicode_input_lsp.server" \
      --prefix PYTHONPATH : "$out/share/unicode-input-lsp"
    runHook postInstall
  '';
  meta = {
    mainProgram = "unicode-input-lsp";
    license = lib.licenses.asl20;
    platforms = [ "aarch64-darwin" "aarch64-linux" "x86_64-linux" ];
  };
}
