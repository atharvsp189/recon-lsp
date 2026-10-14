from recon.commands.info_cmd import app
from recon.config import ReconConfig, save_global_config, save_project_config


def test_info_command_defaults(runner, isolated_env):
    res = runner.invoke(app, [])
    assert res.exit_code == 0
    assert "Recon Info" in res.output
    assert "Version:" in res.output
    assert "Daemon:" in res.output
    assert "stopped" in res.output
    assert "Project: ✗ not found" in res.output


def test_info_command_with_configs_and_running_daemon(
    runner, isolated_env, tmp_path, monkeypatch
):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    cfg = ReconConfig(language="python", repo_path=str(repo_dir))
    save_project_config(cfg, str(repo_dir))
    save_global_config(cfg)

    monkeypatch.setattr("recon.commands.info_cmd.is_daemon_alive", lambda: True)

    res = runner.invoke(app, ["--repo-path", str(repo_dir)])
    assert res.exit_code == 0
    assert "Recon Info" in res.output
    assert "Language:       python" in res.output
    assert "Daemon:         running" in res.output
    assert "Project: ✓ found" in res.output
    assert "Global:  ✓ found" in res.output
