"""Tests for the Click-based CLI."""

import json
from pathlib import Path
from click.testing import CliRunner
import pytest

from fl_studio_mcp.cli import main, get_config_path


@pytest.fixture
def mock_home(tmp_path, monkeypatch):
    """Isolate tests from the real user's ~/.fl_studio_mcp.json file."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Verify the path is now using the tmp_path
    assert str(Path.expanduser(Path("~/.fl_studio_mcp.json"))).startswith(str(tmp_path))
    return tmp_path


def test_cli_help():
    """Verify fl-studio help runs successfully."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "connect" in result.output
    assert "status" in result.output
    assert "play" in result.output
    assert "chord" in result.output


def test_cli_ports():
    """Verify ports command runs."""
    runner = CliRunner()
    result = runner.invoke(main, ["ports"])
    assert result.exit_code == 0
    assert "Available MIDI Output Ports" in result.output


def test_cli_connect_missing_port(mock_home):
    """Verify connecting without port option fails with instructions."""
    runner = CliRunner()
    result = runner.invoke(main, ["connect"])
    assert result.exit_code != 0
    assert "Error: Please specify a MIDI port using --port" in result.output


def test_cli_connect_dry_run(mock_home):
    """Verify connect with dry-run creates a configuration file."""
    runner = CliRunner()
    result = runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
    assert result.exit_code == 0
    assert "Connected to output MIDI port" in result.output

    # Check config was written
    target_config = get_config_path()
    assert target_config.exists()
    with open(target_config, "r") as f:
        data = json.load(f)
    assert data["port_name"] == "Test Port"
    assert data["dry_run"] is True


def test_cli_commands_in_dry_run(mock_home):
    """Verify basic commands function using saved dry-run connection."""
    runner = CliRunner()
    # Connect first
    runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])

    # Test play command
    result = runner.invoke(main, ["play"])
    assert result.exit_code == 0
    play_data = json.loads(result.output)
    assert play_data["dry_run"] is True
    assert play_data["would_send_bytes"] == "F0 7F 7F 06 02 F7"

    # Test stop command
    result = runner.invoke(main, ["stop"])
    assert result.exit_code == 0
    stop_data = json.loads(result.output)
    assert stop_data["dry_run"] is True
    assert stop_data["would_send_bytes"] == "F0 7F 7F 06 01 F7"

    # Test tempo command
    result = runner.invoke(main, ["tempo", "128"])
    assert result.exit_code == 0
    tempo_data = json.loads(result.output)
    assert tempo_data["dry_run"] is True
    assert tempo_data["bpm"] == 128

    # Test volume command
    result = runner.invoke(main, ["channels", "volume", "2", "90"])
    assert result.exit_code == 0
    vol_data = json.loads(result.output)
    assert vol_data["dry_run"] is True
    assert vol_data["channel_index"] == 2
    assert vol_data["volume"] == 90

    # Test chord command
    result = runner.invoke(
        main, ["chord", "C4", "minor", "--start", "96", "--duration", "192"]
    )
    assert result.exit_code == 0
    chord_data = json.loads(result.output)
    assert chord_data["dry_run"] is True


def test_cli_disconnect(mock_home):
    """Verify disconnect clears saved configuration."""
    runner = CliRunner()
    # Connect first
    runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
    target_config = get_config_path()
    assert target_config.exists()

    # Disconnect
    result = runner.invoke(main, ["disconnect"])
    assert result.exit_code == 0
    assert "Disconnected. Saved configuration cleared" in result.output
    assert not target_config.exists()


def test_cli_composition_dry_run(mock_home):
    """Verify composition commands function using saved dry-run connection."""
    runner = CliRunner()
    # Connect first
    runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])

    # Test scale command
    result = runner.invoke(
        main,
        ["composition", "scale", "--root", "C5", "--scale", "minor", "--octaves", "1"],
    )
    assert result.exit_code == 0
    scale_data = json.loads(result.output)
    assert scale_data["dry_run"] is True

    # Test arpeggio command
    result = runner.invoke(
        main,
        [
            "composition",
            "arpeggio",
            "--root",
            "C5",
            "--chord",
            "major",
            "--style",
            "up",
            "--octaves",
            "1",
        ],
    )
    assert result.exit_code == 0
    arp_data = json.loads(result.output)
    assert arp_data["dry_run"] is True

    # Test drums command
    result = runner.invoke(
        main,
        [
            "composition",
            "drums",
            "--mapping",
            '{"0": [1, 0, 0, 1]}',
            "--rhythm",
            "eighth",
        ],
    )
    assert result.exit_code == 0
    drums_data = json.loads(result.output)
    assert drums_data["dry_run"] is True


def test_cli_link_script(tmp_path):
    """Verify link-script command creates target directory and copies scripts."""
    runner = CliRunner()

    # We can pass an explicit destination
    dest_dir = tmp_path / "FL_Studio" / "Settings" / "Hardware"
    result = runner.invoke(main, ["link-script", "--dest", str(dest_dir)])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "success"

    # Check target files were copied
    copied_dir = dest_dir / "FL Studio MCP Bridge"
    assert copied_dir.exists()
    assert (copied_dir / "device_fl_mcp_bridge.py").exists()
    assert (copied_dir / "name.py").exists()


def test_cli_install_config(tmp_path):
    """Verify install-config writes servers to claude config."""
    runner = CliRunner()

    config_file = tmp_path / "claude_desktop_config.json"

    result = runner.invoke(
        main, ["install-config", "--claude-config", str(config_file)]
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "success"

    # Verify file content
    assert config_file.exists()
    with open(config_file, "r") as f:
        config_data = json.load(f)

    assert "fl-studio-mcp" in config_data["mcpServers"]
    assert config_data["mcpServers"]["fl-studio-mcp"]["command"] == "uv"
