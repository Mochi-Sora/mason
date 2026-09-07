# nix/tui.nix — Mason TUI (Ink/React) compiled with tsc and bundled
{ masonNpmLib, ... }:
masonNpmLib.buildNpmPackage {
  dirs = [
    "ui-tui"
    "apps/shared"
  ];

  doCheck = false;

  buildPhase = ''
    # esbuild bundles everything — no need for tsc or vite.
    # Run from the workspace root where node_modules/ lives.
    node ui-tui/scripts/build.mjs
  '';

  installPhase = ''
    runHook preInstall

    mkdir -p $out/lib/mason-tui
    # esbuild writes to ui-tui/dist/ from the source root (no cd).
    cp -r ui-tui/dist $out/lib/mason-tui/dist

    # package.json kept for "type": "module" resolution on `node dist/entry.js`.
    cp ui-tui/package.json $out/lib/mason-tui/

    runHook postInstall
  '';
}
