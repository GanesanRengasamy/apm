import pytest

from apm_cli.utils.github_host import is_valid_fqdn, build_raw_content_url


def test_build_raw_content_url():
    """build_raw_content_url returns the correct raw.githubusercontent.com URL."""
    url = build_raw_content_url("microsoft", "apm", "main", "README.md")
    assert url == "https://raw.githubusercontent.com/microsoft/apm/main/README.md"


def test_build_raw_content_url_nested_path():
    """build_raw_content_url handles nested file paths."""
    url = build_raw_content_url("owner", "repo", "v1.0.0", "agents/api-architect.agent.md")
    assert url == "https://raw.githubusercontent.com/owner/repo/v1.0.0/agents/api-architect.agent.md"


def test_build_raw_content_url_slashed_ref():
    """build_raw_content_url encodes slashes in refs (e.g. feature/foo)."""
    url = build_raw_content_url("owner", "repo", "feature/foo", "README.md")
    assert url == "https://raw.githubusercontent.com/owner/repo/feature%2Ffoo/README.md"


def test_valid_fqdns():
    valid_hosts = [
        "github.com",
        "github.com/user/repo",
        "example.com",
        "sub.example.co.uk",
        "a1b2.example",
        "xn--example.com",  # punycode-like label
        "my-service.localdomain.com",
    ]

    for host in valid_hosts:
        assert is_valid_fqdn(host), f"Expected '{host}' to be valid FQDN"


def test_invalid_fqdns():
    invalid_hosts = [
        "",
        None,  # function treats falsy values as invalid
        "localhost",
        "no_dot",
        "-startdash.com",
        "enddash-.com",
        "two..dots.com",
        "a.-b.com",
        "invalid_domain",
    ]

    for host in invalid_hosts:
        # allow passing None without raising (function handles falsy)
        assert not is_valid_fqdn(host), f"Expected '{host}' to be invalid FQDN"


import os

from apm_cli.utils import github_host


def test_default_host_env_override(monkeypatch):
    monkeypatch.setenv("GITHUB_HOST", "example.ghe.com")
    assert github_host.default_host() == "example.ghe.com"
    monkeypatch.delenv("GITHUB_HOST", raising=False)


def test_is_github_hostname_defaults():
    assert github_host.is_github_hostname(github_host.default_host())
    assert github_host.is_github_hostname("org.ghe.com")
    assert not github_host.is_github_hostname("example.com")


def test_is_azure_devops_hostname():
    """Test Azure DevOps hostname detection."""
    # Valid Azure DevOps hosts
    assert github_host.is_azure_devops_hostname("dev.azure.com")
    assert github_host.is_azure_devops_hostname("mycompany.visualstudio.com")
    assert github_host.is_azure_devops_hostname("contoso.visualstudio.com")
    
    # Invalid hosts
    assert not github_host.is_azure_devops_hostname("github.com")
    assert not github_host.is_azure_devops_hostname("example.com")
    assert not github_host.is_azure_devops_hostname("azure.com")
    assert not github_host.is_azure_devops_hostname("visualstudio.com")  # Must have org prefix
    assert not github_host.is_azure_devops_hostname(None)
    assert not github_host.is_azure_devops_hostname("")


def test_is_supported_git_host():
    """Test unified Git host detection supporting all platforms."""
    # GitHub hosts
    assert github_host.is_supported_git_host("github.com")
    assert github_host.is_supported_git_host("company.ghe.com")
    
    # Azure DevOps hosts
    assert github_host.is_supported_git_host("dev.azure.com")
    assert github_host.is_supported_git_host("mycompany.visualstudio.com")
    
    # Generic git hosts (supported via valid FQDN)
    assert github_host.is_supported_git_host("gitlab.com")
    assert github_host.is_supported_git_host("bitbucket.org")
    assert github_host.is_supported_git_host("gitea.example.com")
    assert github_host.is_supported_git_host("git.company.internal")
    
    # Invalid hostnames (not valid FQDNs)
    assert not github_host.is_supported_git_host("localhost")
    assert not github_host.is_supported_git_host(None)
    assert not github_host.is_supported_git_host("")


def test_is_supported_git_host_with_custom_host(monkeypatch):
    """Test that GITHUB_HOST env var adds custom host to supported list."""
    # Set a custom Azure DevOps Server host
    monkeypatch.setenv("GITHUB_HOST", "ado.mycompany.internal")
    
    # Custom host should now be supported
    assert github_host.is_supported_git_host("ado.mycompany.internal")
    
    # Standard hosts should still work
    assert github_host.is_supported_git_host("github.com")
    assert github_host.is_supported_git_host("dev.azure.com")
    
    monkeypatch.delenv("GITHUB_HOST", raising=False)


def test_sanitize_token_url_in_message():
    host = github_host.default_host()
    msg = f"fatal: Authentication failed for 'https://ghp_secret@{host}/user/repo.git'"
    sanitized = github_host.sanitize_token_url_in_message(msg, host=host)
    assert f"***@{host}" in sanitized


def test_unsupported_host_error_message():
    """Test that unsupported host error provides actionable guidance."""
    error_msg = github_host.unsupported_host_error("github.company.com")
    
    # Should mention the hostname
    assert "github.company.com" in error_msg
    
    # Should list supported hosts
    assert "github.com" in error_msg
    assert "*.ghe.com" in error_msg
    assert "dev.azure.com" in error_msg
    
    # Should provide fix instructions for all platforms
    assert "export GITHUB_HOST=" in error_msg
    assert "$env:GITHUB_HOST" in error_msg
    assert "set GITHUB_HOST=" in error_msg


def test_unsupported_host_error_shows_current_host(monkeypatch):
    """Test that error shows current GITHUB_HOST if set."""
    monkeypatch.setenv("GITHUB_HOST", "other.company.com")
    
    error_msg = github_host.unsupported_host_error("github.company.com")
    
    # Should show the mismatch
    assert "other.company.com" in error_msg
    assert "github.company.com" in error_msg
    
    monkeypatch.delenv("GITHUB_HOST", raising=False)


# Azure DevOps URL builder tests

def test_build_ado_https_clone_url():
    """Test Azure DevOps HTTPS URL construction."""
    # Without token
    url = github_host.build_ado_https_clone_url("dmeppiel-org", "market-js-app", "compliance-rules")
    assert url == "https://dev.azure.com/dmeppiel-org/market-js-app/_git/compliance-rules"
    
    # With token
    url = github_host.build_ado_https_clone_url("dmeppiel-org", "market-js-app", "compliance-rules", token="mytoken")
    assert url == "https://mytoken@dev.azure.com/dmeppiel-org/market-js-app/_git/compliance-rules"
    
    # With custom host (ADO Server)
    url = github_host.build_ado_https_clone_url("myorg", "myproject", "myrepo", host="ado.company.internal")
    assert url == "https://ado.company.internal/myorg/myproject/_git/myrepo"


def test_build_ado_ssh_url():
    """Test Azure DevOps SSH URL construction."""
    url = github_host.build_ado_ssh_url("dmeppiel-org", "market-js-app", "compliance-rules")
    assert url == "git@ssh.dev.azure.com:v3/dmeppiel-org/market-js-app/compliance-rules"


def test_build_ado_ssh_url_server():
    """Test Azure DevOps Server SSH URL construction for on-premises."""
    # Custom host should use server format
    url = github_host.build_ado_ssh_url("myorg", "myproject", "myrepo", host="ado.company.internal")
    assert url == "ssh://git@ado.company.internal/myorg/myproject/_git/myrepo"
    
    # Cloud host should use cloud format
    url = github_host.build_ado_ssh_url("myorg", "myproject", "myrepo", host="ssh.dev.azure.com")
    assert url == "git@ssh.dev.azure.com:v3/myorg/myproject/myrepo"


def test_build_ado_api_url():
    """Test Azure DevOps API URL construction."""
    url = github_host.build_ado_api_url("myorg", "myproject", "myrepo", "path/to/file.md")
    assert url.startswith("https://dev.azure.com/myorg/myproject/_apis/git/repositories/myrepo/items")
    assert "path=path%2Fto%2Ffile.md" in url
    assert "versionDescriptor.version=main" in url  # default ref is "main"


# Gitea hostname detection tests

def test_is_gitea_hostname():
    """Test Gitea hostname detection."""
    # Valid Gitea hosts
    assert github_host.is_gitea_hostname("gitea.com")
    assert github_host.is_gitea_hostname("www.gitea.com")
    assert github_host.is_gitea_hostname("git.gitea.io")
    assert github_host.is_gitea_hostname("myteam.gitea.io")
    
    # Invalid hosts
    assert not github_host.is_gitea_hostname("github.com")
    assert not github_host.is_gitea_hostname("gitlab.com")
    assert not github_host.is_gitea_hostname("example.com")
    assert not github_host.is_gitea_hostname("gitea.com/user/repo")  # has path
    assert not github_host.is_gitea_hostname(None)
    assert not github_host.is_gitea_hostname("")


def test_is_supported_git_host_gitea():
    """Test that Gitea hosts are supported."""
    assert github_host.is_supported_git_host("gitea.com")
    assert github_host.is_supported_git_host("www.gitea.com")
    assert github_host.is_supported_git_host("myteam.gitea.io")


# Gitea URL builder tests

def test_build_gitea_https_clone_url():
    """Test Gitea HTTPS URL construction."""
    # Without token
    url = github_host.build_gitea_https_clone_url("owner/repo")
    assert url == "https://gitea.com/owner/repo.git"
    
    # With token
    url = github_host.build_gitea_https_clone_url("owner/repo", token="mytoken")
    assert url == "https://mytoken@gitea.com/owner/repo.git"
    
    # With custom host (self-hosted Gitea)
    url = github_host.build_gitea_https_clone_url("owner/repo", host="gitea.company.internal")
    assert url == "https://gitea.company.internal/owner/repo.git"
    
    # With token and custom host
    url = github_host.build_gitea_https_clone_url("owner/repo", token="mytoken", host="git.company.com")
    assert url == "https://mytoken@git.company.com/owner/repo.git"


def test_build_gitea_ssh_url():
    """Test Gitea SSH URL construction."""
    url = github_host.build_gitea_ssh_url("owner/repo")
    assert url == "git@gitea.com:owner/repo.git"
    
    # With custom host (self-hosted Gitea)
    url = github_host.build_gitea_ssh_url("owner/repo", host="gitea.company.internal")
    assert url == "git@gitea.company.internal:owner/repo.git"


def test_build_gitea_api_url():
    """Test Gitea API URL construction."""
    url = github_host.build_gitea_api_url("owner", "repo", "path/to/file.md")
    assert url.startswith("https://gitea.com/api/v1/repos/owner/repo/contents/")
    assert "path%2Fto%2Ffile.md" in url  # path is URL-encoded
    assert "ref=main" in url
    
    # With custom ref
    url = github_host.build_gitea_api_url("owner", "repo", "README.md", ref="v1.0.0")
    assert "ref=v1.0.0" in url
    
    # With custom host
    url = github_host.build_gitea_api_url("owner", "repo", "README.md", host="gitea.company.com")
    assert url.startswith("https://gitea.company.com/api/v1/")


def test_build_gitea_archive_url():
    """Test Gitea archive URL construction."""
    urls = github_host.build_gitea_archive_url("owner", "repo", ref="main")
    assert len(urls) == 2
    assert "https://gitea.com/owner/repo/archive/main.zip" in urls
    assert "https://gitea.com/owner/repo/archive/refs/heads/main.zip" in urls
    
    # With custom host
    urls = github_host.build_gitea_archive_url("owner", "repo", ref="v1.0", host="gitea.company.com")
    assert all("gitea.company.com" in url for url in urls)


def test_gitea_url_encodes_special_characters():
    """Test that Gitea URL builders properly encode special characters in paths."""
    # Path with spaces and special chars should be URL-encoded
    url = github_host.build_gitea_api_url("owner", "repo", "path/with spaces/file.md", ref="feature/branch")
    assert "path%2Fwith%20spaces%2Ffile.md" in url
    assert "feature%2Fbranch" in url
    url = github_host.build_ado_api_url("dmeppiel-org", "market-js-app", "compliance-rules", "apm.yml", "main")
    assert "/_apis/git/repositories/compliance-rules/items" in url
    assert "path=apm.yml" in url
    assert "versionDescriptor.version=main" in url
    assert "api-version=7.0" in url


# Unsupported host error message tests

def test_unsupported_host_error_message():
    """Test that unsupported host error provides actionable guidance."""
    error_msg = github_host.unsupported_host_error("github.company.com")
    
    # Should mention the hostname
    assert "github.company.com" in error_msg
    
    # Should list supported hosts
    assert "github.com" in error_msg
    assert "*.ghe.com" in error_msg
    assert "dev.azure.com" in error_msg
    
    # Should provide fix instructions for all platforms
    assert "export GITHUB_HOST=" in error_msg
    assert "$env:GITHUB_HOST" in error_msg
    assert "set GITHUB_HOST=" in error_msg


def test_unsupported_host_error_with_context():
    """Test that context message is included when provided."""
    error_msg = github_host.unsupported_host_error("//evil.com", context="Protocol-relative URLs are not supported")
    
    # Should include the context
    assert "Protocol-relative URLs are not supported" in error_msg
    
    # Should still include standard guidance
    assert "github.com" in error_msg
    assert "GITHUB_HOST" in error_msg


def test_unsupported_host_error_shows_current_host(monkeypatch):
    """Test that error shows current GITHUB_HOST if set."""
    monkeypatch.setenv("GITHUB_HOST", "other.company.com")
    
    error_msg = github_host.unsupported_host_error("github.company.com")
    
    # Should show the mismatch
    assert "other.company.com" in error_msg
    assert "github.company.com" in error_msg
    
    monkeypatch.delenv("GITHUB_HOST", raising=False)
