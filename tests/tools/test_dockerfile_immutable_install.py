"""Contract tests for the Docker image's immutable /opt/mason install tree."""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO_ROOT / "Dockerfile"


def _dockerfile_text() -> str:
    return DOCKERFILE.read_text()


def test_dockerfile_makes_opt_mason_readonly_for_mason_user() -> None:
    text = _dockerfile_text()

    # --chmod on the source COPY bakes read-only perms at copy time instead
    # of a separate chmod -R pass (which walked ~30k files — #49113).
    assert "COPY --link --chmod=a+rX,go-w . ." in text
    # The old tree-walking passes must not be present.
    assert "chown -R root:root /opt/mason" not in text
    assert "chmod -R a+rX /opt/mason" not in text
    assert "chmod -R a-w /opt/mason" not in text


def test_dockerfile_does_not_chown_install_trees_to_mason() -> None:
    text = _dockerfile_text()
    forbidden_patterns = (
        r"chown\s+-R\s+mason:mason\s+/opt/mason/\.venv",
        r"chown\s+-R\s+mason:mason\s+/opt/mason/ui-tui",
        r"chown\s+-R\s+mason:mason\s+/opt/mason/gateway",
        r"chown\s+-R\s+mason:mason\s+/opt/mason/node_modules",
    )
    for pattern in forbidden_patterns:
        assert not re.search(pattern, text), (
            "runtime install trees under /opt/mason must stay immutable; "
            f"found forbidden pattern {pattern!r}"
        )


def test_dockerfile_bakes_code_scoped_install_method_stamp() -> None:
    """The 'docker' install-method stamp is baked next to the code.

    detect_install_method() reads the code-scoped stamp
    (/opt/mason/.install_method) first; baking it at build time keeps the
    published image self-identifying as 'docker' WITHOUT writing into the
    shared $MASON_HOME data volume (which a host install may also use).
    The stamp is created by root in the shim-wiring RUN block; the mason
    user can't modify it (go-w from the --chmod on the source COPY).
    """
    text = _dockerfile_text()
    assert "printf 'docker\\n' > /opt/mason/.install_method" in text

    # The stamp must be in the RUN block that wires the exec shim.
    shim_block = re.search(
        r"RUN mkdir -p /opt/mason/bin && \\\n"
        r"(?:.*\\\n)+?"
        r"\s+printf 'docker\\n' > /opt/mason/\.install_method",
        text,
    )
    assert shim_block, "install-method stamp must be in the shim-wiring RUN block"


def test_dockerfile_redirects_lazy_installs_to_durable_target() -> None:
    """Immutable image seals the venv but redirects lazy installs to the
    writable data volume, so opt-in backends still install at first use
    without being able to break the sealed core.

    Guards the contract between the Dockerfile env var, the stage2-hook
    seeding, and tools/lazy_deps.py — these three must agree on the path.
    """
    text = _dockerfile_text()
    target = "/opt/data/lazy-packages"

    # The redirect target must be set AND must live under the data volume,
    # never under the immutable /opt/mason tree.
    assert f"ENV MASON_LAZY_INSTALL_TARGET={target}" in text
    assert target.startswith("/opt/data/"), "target must be on the durable volume"
    assert "ENV MASON_LAZY_INSTALL_TARGET=/opt/mason" not in text

    # The seal flag must still be present — the redirect rides on top of it,
    # it does not replace it.
    assert "ENV MASON_DISABLE_LAZY_INSTALLS=1" in text

    # stage2-hook must seed + chown the target dir so first-use installs
    # succeed as the unprivileged mason runtime user.
    stage2 = (REPO_ROOT / "docker" / "stage2-hook.sh").read_text()
    assert '"$MASON_HOME/lazy-packages"' in stage2, (
        "stage2-hook.sh must create the lazy-packages dir on the data volume"
    )
    assert "lazy-packages" in stage2.split("for sub in", 1)[1].split(";", 1)[0], (
        "lazy-packages must be in the per-boot chown subdir list so it stays "
        "mason-owned"
    )


def test_dockerfile_bakes_photon_sidecar_deps() -> None:
    """The Photon sidecar's node_modules must be baked at build time (NS-606).

    The install tree is immutable at runtime, so a lazy `npm ci` on first
    connect would hit EROFS. Baking the deps (from the committed lockfile,
    which also runs the spectrum-ts postinstall patch) makes the hosted
    happy path install-free. Guards the contract between the Dockerfile
    and plugins/platforms/photon/sidecar_paths.resolve_sidecar_dir, which
    runs in place only when the baked deps exist and match the lockfile.
    """
    text = _dockerfile_text()

    assert "plugins/platforms/photon/sidecar/package-lock.json" in text
    assert re.search(
        r"RUN cd plugins/platforms/photon/sidecar && \\\n\s+npm ci", text
    ), "sidecar deps must be installed with `npm ci` (deterministic, runs postinstall patch)"
    # Immutability contract: never chown the sidecar tree to the runtime user.
    assert not re.search(
        r"chown\s+-R\s+mason:mason\s+/opt/mason/plugins", text
    )
