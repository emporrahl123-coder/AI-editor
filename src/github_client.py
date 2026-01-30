"""
GitHub API client for interacting with repositories
"""

import requests
import base64
import json
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class GitHubFile:
    """Represents a GitHub file"""
    path: str
    content: str
    sha: Optional[str] = None
    size: Optional[int] = None
    encoding: Optional[str] = None
    type: Optional[str] = None

@dataclass
class RepositoryInfo:
    """Repository information"""
    owner: str
    name: str
    full_name: str
    description: Optional[str] = None
    default_branch: str = "main"
    private: bool = False
    fork: bool = False

class GitHubClient:
    """Client for GitHub API v3"""
    
    def __init__(self, token: str, api_url: str = "https://api.github.com"):
        """
        Initialize GitHub client
        
        Args:
            token: GitHub Personal Access Token
            api_url: GitHub API base URL
        """
        self.token = token
        self.api_url = api_url.rstrip('/')
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitHub-AI-Editor/1.0"
        }
        
        # Test connection
        self._test_connection()
    
    def _test_connection(self):
        """Test GitHub API connection"""
        try:
            response = requests.get(
                f"{self.api_url}/user",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            user_data = response.json()
            logger.info(f"Connected to GitHub as {user_data.get('login')}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to GitHub: {e}")
            raise
    
    def parse_repo_url(self, url: str) -> Tuple[str, str]:
        """
        Parse GitHub repository URL to extract owner and repo name
        
        Args:
            url: GitHub repository URL
            
        Returns:
            Tuple of (owner, repo_name)
        """
        # Remove .git suffix and trailing slash
        url = url.rstrip('/').rstrip('.git')
        
        # Parse URL
        parsed = urlparse(url)
        
        # Extract path parts
        path_parts = parsed.path.strip('/').split('/')
        
        if len(path_parts) < 2:
            raise ValueError(f"Invalid GitHub URL: {url}")
        
        owner = path_parts[0]
        repo_name = path_parts[1]
        
        return owner, repo_name
    
    def get_repository_info(self, owner: str, repo: str) -> RepositoryInfo:
        """
        Get repository information
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            RepositoryInfo object
        """
        url = f"{self.api_url}/repos/{owner}/{repo}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            return RepositoryInfo(
                owner=data.get('owner', {}).get('login', owner),
                name=data.get('name', repo),
                full_name=data.get('full_name', f"{owner}/{repo}"),
                description=data.get('description'),
                default_branch=data.get('default_branch', 'main'),
                private=data.get('private', False),
                fork=data.get('fork', False)
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get repository info: {e}")
            raise
    
    def get_file_content(self, owner: str, repo: str, filepath: str, 
                        ref: Optional[str] = None) -> GitHubFile:
        """
        Get content of a specific file
        
        Args:
            owner: Repository owner
            repo: Repository name
            filepath: Path to file in repository
            ref: Git reference (branch, tag, or commit)
            
        Returns:
            GitHubFile object
        """
        url = f"{self.api_url}/repos/{owner}/{repo}/contents/{filepath}"
        params = {}
        
        if ref:
            params['ref'] = ref
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Decode content if it's base64 encoded
            content = data.get('content', '')
            if data.get('encoding') == 'base64':
                content = base64.b64decode(content).decode('utf-8')
            
            return GitHubFile(
                path=data.get('path', filepath),
                content=content,
                sha=data.get('sha'),
                size=data.get('size'),
                encoding=data.get('encoding'),
                type=data.get('type')
            )
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise FileNotFoundError(f"File not found: {filepath}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get file content: {e}")
            raise
    
    def get_repository_tree(self, owner: str, repo: str, 
                          ref: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get repository tree (list of all files)
        
        Args:
            owner: Repository owner
            repo: Repository name
            ref: Git reference
            
        Returns:
            List of file/directory objects
        """
        url = f"{self.api_url}/repos/{owner}/{repo}/git/trees"
        
        # Get default branch if ref not provided
        if not ref:
            repo_info = self.get_repository_info(owner, repo)
            ref = repo_info.default_branch
        
        # Get the tree SHA for the ref
        ref_url = f"{self.api_url}/repos/{owner}/{repo}/git/refs/heads/{ref}"
        try:
            response = requests.get(ref_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            ref_data = response.json()
            tree_sha = ref_data['object']['sha']
        except:
            # Fallback: try to get the commit directly
            commit_url = f"{self.api_url}/repos/{owner}/{repo}/commits/{ref}"
            response = requests.get(commit_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            commit_data = response.json()
            tree_sha = commit_data['commit']['tree']['sha']
        
        # Get recursive tree
        params = {'recursive': '1'}
        url = f"{self.api_url}/repos/{owner}/{repo}/git/trees/{tree_sha}"
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            tree_data = response.json()
            
            return tree_data.get('tree', [])
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get repository tree: {e}")
            raise
    
    def create_or_update_file(self, owner: str, repo: str, filepath: str, 
                            content: str, message: str, 
                            sha: Optional[str] = None, 
                            branch: Optional[str] = None) -> Dict[str, Any]:
        """
        Create or update a file in repository
        
        Args:
            owner: Repository owner
            repo: Repository name
            filepath: Path to file
            content: New file content
            message: Commit message
            sha: SHA of existing file (for updates)
            branch: Branch to commit to
            
        Returns:
            API response
        """
        url = f"{self.api_url}/repos/{owner}/{repo}/contents/{filepath}"
        
        data = {
            "message": message,
            "content": base64.b64encode(content.encode('utf-8')).decode('ascii'),
        }
        
        if sha:
            data["sha"] = sha
        
        if branch:
            data["branch"] = branch
        
        try:
            response = requests.put(url, headers=self.headers, json=data, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create/update file: {e}")
            raise
    
    def create_branch(self, owner: str, repo: str, 
                     branch_name: str, from_branch: str = "main") -> Dict[str, Any]:
        """
        Create a new branch
        
        Args:
            owner: Repository owner
            repo: Repository name
            branch_name: New branch name
            from_branch: Source branch
            
        Returns:
            API response
        """
        # Get SHA of the source branch
        ref_url = f"{self.api_url}/repos/{owner}/{repo}/git/refs/heads/{from_branch}"
        
        try:
            response = requests.get(ref_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            ref_data = response.json()
            sha = ref_data['object']['sha']
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                # Try with 'master' as fallback
                ref_url = f"{self.api_url}/repos/{owner}/{repo}/git/refs/heads/master"
                response = requests.get(ref_url, headers=self.headers, timeout=10)
                response.raise_for_status()
                ref_data = response.json()
                sha = ref_data['object']['sha']
            else:
                raise
        
        # Create new branch
        url = f"{self.api_url}/repos/{owner}/{repo}/git/refs"
        data = {
            "ref": f"refs/heads/{branch_name}",
            "sha": sha
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=data, timeout=30)
            
            # Check if branch already exists (422 error)
            if response.status_code == 422:
                logger.warning(f"Branch {branch_name} already exists")
                return {"status": "exists", "branch": branch_name}
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create branch: {e}")
            raise
    
    def create_pull_request(self, owner: str, repo: str, title: str, 
                          body: str, head: str, base: str = "main") -> Dict[str, Any]:
        """
        Create a pull request
        
        Args:
            owner: Repository owner
            repo: Repository name
            title: PR title
            body: PR description
            head: Source branch
            base: Target branch
            
        Returns:
            API response
        """
        url = f"{self.api_url}/repos/{owner}/{repo}/pulls"
        
        data = {
            "title": title,
            "body": body,
            "head": head,
            "base": base
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=data, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create pull request: {e}")
            raise
    
    def get_branch(self, owner: str, repo: str, branch: str) -> Optional[Dict[str, Any]]:
        """
        Get branch information
        
        Args:
            owner: Repository owner
            repo: Repository name
            branch: Branch name
            
        Returns:
            Branch information or None if not found
        """
        url = f"{self.api_url}/repos/{owner}/{repo}/branches/{branch}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    def list_branches(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        """
        List all branches
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            List of branches
        """
        url = f"{self.api_url}/repos/{owner}/{repo}/branches"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to list branches: {e}")
            raise
    
    def test_permissions(self, owner: str, repo: str) -> Dict[str, bool]:
        """
        Test permissions for the repository
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            Dictionary of permissions
        """
        url = f"{self.api_url}/repos/{owner}/{repo}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            repo_data = response.json()
            
            permissions = repo_data.get('permissions', {})
            
            return {
                "admin": permissions.get('admin', False),
                "push": permissions.get('push', False),
                "pull": permissions.get('pull', True),
                "can_create_pr": permissions.get('push', False) or permissions.get('admin', False)
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to test permissions: {e}")
            return {
                "admin": False,
                "push": False,
                "pull": False,
                "can_create_pr": False
            }
