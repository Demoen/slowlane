"""CLI integration tests."""

from typer.testing import CliRunner

from slowlane.cli.main import app

runner = CliRunner()


class TestCLI:
    """Tests for CLI commands."""

    def test_help(self) -> None:
        """Test --help shows usage."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "slowlane" in result.stdout.lower()

    def test_version(self) -> None:
        """Test version command."""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.stdout

    def test_spaceauth_help(self) -> None:
        """Test spaceauth --help."""
        result = runner.invoke(app, ["spaceauth", "--help"])
        assert result.exit_code == 0
        assert "login" in result.stdout
        assert "export" in result.stdout
        assert "verify" in result.stdout

    def test_asc_help(self) -> None:
        """Test asc --help."""
        result = runner.invoke(app, ["asc", "--help"])
        assert result.exit_code == 0
        assert "apps" in result.stdout
        assert "builds" in result.stdout
        assert "testflight" in result.stdout

    def test_signing_help(self) -> None:
        """Test signing --help."""
        result = runner.invoke(app, ["signing", "--help"])
        assert result.exit_code == 0
        assert "certs" in result.stdout
        assert "profiles" in result.stdout

    def test_upload_help(self) -> None:
        """Test upload --help."""
        result = runner.invoke(app, ["upload", "--help"])
        assert result.exit_code == 0
        assert "ipa" in result.stdout

    def test_env_help(self) -> None:
        """Test env --help."""
        result = runner.invoke(app, ["env", "--help"])
        assert result.exit_code == 0
        assert "print" in result.stdout

    def test_spaceauth_doctor(self) -> None:
        """Test spaceauth doctor runs without error."""
        result = runner.invoke(app, ["spaceauth", "doctor"])
        assert result.exit_code == 0
        assert "Diagnostics" in result.stdout or "Check" in result.stdout


class TestEnvCommands:
    """Tests for env command functionality."""

    def test_env_print_no_config(self) -> None:
        """Test env print with no credentials configured."""
        result = runner.invoke(app, ["env", "print"])
        # Should indicate no credentials or print empty
        assert result.exit_code == 0

    def test_env_print_github_platform(self) -> None:
        """Test env print with github platform."""
        result = runner.invoke(app, ["env", "print", "--platform", "github"])
        assert result.exit_code == 0

    def test_env_print_gitlab_platform(self) -> None:
        """Test env print with gitlab platform."""
        result = runner.invoke(app, ["env", "print", "--platform", "gitlab"])
        assert result.exit_code == 0

    def test_env_print_azure_platform(self) -> None:
        """Test env print with azure platform."""
        result = runner.invoke(app, ["env", "print", "--platform", "azure"])
        assert result.exit_code == 0

    def test_env_print_generic_platform(self) -> None:
        """Test env print with generic platform."""
        result = runner.invoke(app, ["env", "print", "--platform", "generic"])
        assert result.exit_code == 0

    def test_env_setup_github(self) -> None:
        """Test env setup instructions for GitHub."""
        result = runner.invoke(app, ["env", "setup", "--platform", "github"])
        assert result.exit_code == 0
        assert "GitHub Actions" in result.stdout
        assert "secrets" in result.stdout.lower()

    def test_env_setup_gitlab(self) -> None:
        """Test env setup instructions for GitLab."""
        result = runner.invoke(app, ["env", "setup", "--platform", "gitlab"])
        assert result.exit_code == 0
        assert "GitLab CI" in result.stdout

    def test_env_setup_azure(self) -> None:
        """Test env setup instructions for Azure DevOps."""
        result = runner.invoke(app, ["env", "setup", "--platform", "azure"])
        assert result.exit_code == 0
        assert "Azure DevOps" in result.stdout


class TestSpaceauthCommands:
    """Tests for spaceauth command functionality."""

    def test_spaceauth_verify_no_session(self) -> None:
        """Test spaceauth verify with no session."""
        result = runner.invoke(app, ["spaceauth", "verify"])
        # Should fail gracefully with no session
        assert result.exit_code != 0 or "No session" in result.stdout or "not found" in result.stdout.lower()

    def test_spaceauth_export_no_session(self) -> None:
        """Test spaceauth export with no session."""
        result = runner.invoke(app, ["spaceauth", "export"])
        # Should indicate no session available
        assert "session" in result.stdout.lower() or result.exit_code != 0


class TestAscCommands:
    """Tests for asc command subcommands."""

    def test_asc_apps_help(self) -> None:
        """Test asc apps --help."""
        result = runner.invoke(app, ["asc", "apps", "--help"])
        assert result.exit_code == 0
        assert "list" in result.stdout

    def test_asc_builds_help(self) -> None:
        """Test asc builds --help."""
        result = runner.invoke(app, ["asc", "builds", "--help"])
        assert result.exit_code == 0
        assert "list" in result.stdout

    def test_asc_testflight_help(self) -> None:
        """Test asc testflight --help."""
        result = runner.invoke(app, ["asc", "testflight", "--help"])
        assert result.exit_code == 0
        assert "testers" in result.stdout
        assert "groups" in result.stdout


class TestSigningCommands:
    """Tests for signing command subcommands."""

    def test_signing_certs_help(self) -> None:
        """Test signing certs --help."""
        result = runner.invoke(app, ["signing", "certs", "--help"])
        assert result.exit_code == 0
        assert "list" in result.stdout

    def test_signing_profiles_help(self) -> None:
        """Test signing profiles --help."""
        result = runner.invoke(app, ["signing", "profiles", "--help"])
        assert result.exit_code == 0
        assert "list" in result.stdout

