from types import SimpleNamespace
from unittest.mock import patch

from mason_cli.config import recommended_update_command
from mason_cli.main import cmd_update
from tools.skills_hub_official import OptionalSkillSource


def test_recommended_update_command_defaults_to_mason_update(monkeypatch):
    monkeypatch.delenv("MASON_MANAGED", raising=False)

    # Also short-circuit the .managed marker path — CI runners may have an
    # ambient ~/.mason/.managed if a prior test left MASON_HOME pointing
    # somewhere with that marker, which would make get_managed_update_command()
    # return "Update your Nix flake input ..." instead of falling through to
    # detect_install_method().
    with patch("mason_cli.config.get_managed_update_command", return_value=None), \
         patch("mason_cli.config.detect_install_method", return_value="git"):
        assert recommended_update_command() == "mason update"


def test_optional_skill_source_honors_env_override(monkeypatch, tmp_path):
    optional_dir = tmp_path / "optional-skills"
    optional_dir.mkdir()
    monkeypatch.setenv("MASON_OPTIONAL_SKILLS", str(optional_dir))

    source = OptionalSkillSource()

    assert source._optional_dir == optional_dir
