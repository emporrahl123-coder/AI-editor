"""
Tests for GitHub client
"""

import pytest
import responses
from unittest.mock import Mock, patch
from src.github_client import GitHubClient, RepositoryInfo

class TestGitHubClient:
    
    def test_parse_repo_url_https(self):
        """Test parsing HTTPS GitHub URL"""
        client = GitHubClient("test_token")
        
        owner, repo = client.parse_repo_url("https://github.com/owner/repo")
        assert owner == "owner"
        assert repo == "repo"
        
        owner, repo = client.parse_repo_url("https://github.com/owner/repo.git")
        assert owner == "owner"
        assert repo == "repo"
    
    def test_parse_repo_url_ssh(self):
        """Test parsing SSH GitHub URL"""
        client = GitHubClient("test_token")
        
        owner, repo = client.parse_repo_url("git@github.com:owner/repo.git")
        assert owner == "owner"
        assert repo == "repo"
    
    @responses.activate
    def test_get_repository_info(self):
        """Test getting repository information"""
        client = GitHubClient("test_token")
        
        responses.add(
            responses.GET,
            "https://api.github.com/repos/owner/repo",
            json={
                "name": "repo",
                "full_name": "owner/repo",
                "description": "Test repository",
                "owner": {"login": "owner"},
                "private": False,
                "fork": False,
                "default_branch": "main"
            },
            status=200
        )
        
        info = client.get_repository_info("owner", "repo")
        
        assert isinstance(info, RepositoryInfo)
        assert info.owner == "owner"
        assert info.name == "repo"
        assert info.full_name == "owner/repo"
        assert info.description == "Test repository"
        assert info.default_branch == "main"
        assert info.private is False
        assert info.fork is False
    
    @responses.activate
    def test_get_file_content(self):
        """Test getting file content"""
        client = GitHubClient("test_token")
        
        responses.add(
            responses.GET,
            "https://api.github.com/repos/owner/repo/contents/test.py",
            json={
                "path": "test.py",
                "content": "cHJpbnQoIkhlbGxvIFdvcmxkIik=",  # "print("Hello World")" in base64
                "encoding": "base64",
                "sha": "abc123",
                "size": 25
            },
            status=200
        )
        
        file = client.get_file_content("owner", "repo", "test.py")
        
        assert file.path == "test.py"
        assert file.content == "print(\"Hello World\")"
        assert file.sha == "abc123"
        assert file.size == 25
    
    @responses.activate
    def test_create_branch(self):
        """Test creating a new branch"""
        client = GitHubClient("test_token")
        
        # Mock get branch SHA
        responses.add(
            responses.GET,
            "https://api.github.com/repos/owner/repo/git/refs/heads/main",
            json={
                "object": {"sha": "abc123"}
            },
            status=200
        )
        
        # Mock create branch
        responses.add(
            responses.POST,
            "https://api.github.com/repos/owner/repo/git/refs",
            json={
                "ref": "refs/heads/test-branch",
                "object": {"sha": "abc123"}
            },
            status=201
        )
        
        result = client.create_branch("owner", "repo", "test-branch")
        
        assert "ref" in result
        assert result["ref"] == "refs/heads/test-branch"
    
    @responses.activate
    def test_create_pull_request(self):
        """Test creating a pull request"""
        client = GitHubClient("test_token")
        
        responses.add(
            responses.POST,
            "https://api.github.com/repos/owner/repo/pulls",
            json={
                "number": 1,
                "title": "Test PR",
                "html_url": "https://github.com/owner/repo/pull/1"
            },
            status=201
        )
        
        result = client.create_pull_request(
            "owner", "repo",
            title="Test PR",
            body="Test description",
            head="feature",
            base="main"
        )
        
        assert result["number"] == 1
        assert result["title"] == "Test PR"
        assert result["html_url"] == "https://github.com/owner/repo/pull/1"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
