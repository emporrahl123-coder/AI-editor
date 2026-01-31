"""
Main repository management and orchestration logic
"""

import os
import json
import tempfile
import shutil
import logging
import time
import traceback
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
import re
import hashlib

from git import Repo, GitCommandError
from .github_client import GitHubClient, RepositoryInfo
from .code_analyzer import CodeAnalyzer
from .ai_editor import AIEditor, EditPlan, EditInstruction
from .config import Config

logger = logging.getLogger(__name__)

@dataclass
class RepositoryContext:
    """Context for a repository being edited"""
    repo_url: str
    owner: str
    repo_name: str
    repo_info: Optional[RepositoryInfo] = None
    local_path: Optional[str] = None
    temp_dir: Optional[str] = None
    structure: Dict[str, Any] = field(default_factory=dict)
    important_files: List[str] = field(default_factory=list)
    key_files_content: Dict[str, str] = field(default_factory=dict)
    languages: List[str] = field(default_factory=list)
    file_count: int = 0
    default_branch: str = "main"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for AI prompts"""
        return {
            "repo_url": self.repo_url,
            "owner": self.owner,
            "repo_name": self.repo_name,
            "description": self.repo_info.description if self.repo_info else "",
            "default_branch": self.default_branch,
            "structure": self.structure,
            "important_files": self.important_files,
            "key_files": self.key_files_content,
            "languages": self.languages,
            "file_count": self.file_count
        }

@dataclass
class FileChange:
    """Represents a file change"""
    file_path: str
    original_content: str
    new_content: str
    change_type: str  # "modified", "created", "deleted"
    language: str
    validation_result: Dict[str, Any]
    review_result: Optional[Dict[str, Any]] = None
    explanation: Optional[str] = None

@dataclass
class EditResult:
    """Result of an edit operation"""
    success: bool
    changes: List[FileChange]
    plan: Optional[EditPlan] = None
    summary: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    branch_name: Optional[str] = None
    pr_url: Optional[str] = None

class RepositoryManager:
    """Manages repository operations and orchestration"""
    
    def __init__(self, config: Config):
        """
        Initialize repository manager
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.github = GitHubClient(config.github.token, config.github.api_url)
        self.analyzer = CodeAnalyzer()
        self.ai_editor = AIEditor(
            api_key=config.openai.api_key,
            model=config.openai.model,
            max_tokens=config.openai.max_tokens,
            temperature=config.openai.temperature
        )
        
        # Create temp directory for clones
        self.temp_base = Path("temp/repos")
        self.temp_base.mkdir(parents=True, exist_ok=True)
        
        # Cache for repository contexts
        self.context_cache: Dict[str, RepositoryContext] = {}
    
    def analyze_repository(self, repo_url: str) -> RepositoryContext:
        """
        Analyze repository structure and content
        
        Args:
            repo_url: GitHub repository URL
            
        Returns:
            RepositoryContext object
        """
        logger.info(f"Analyzing repository: {repo_url}")
        
        # Check cache first
        cache_key = hashlib.md5(repo_url.encode()).hexdigest()
        if cache_key in self.context_cache:
            logger.info(f"Using cached context for {repo_url}")
            return self.context_cache[cache_key]
        
        try:
            # Parse URL
            owner, repo_name = self.github.parse_repo_url(repo_url)
            
            # Get repository info
            repo_info = self.github.get_repository_info(owner, repo_name)
            
            # Clone repository locally
            temp_dir = tempfile.mkdtemp(prefix="github_ai_", dir=self.temp_base)
            local_path = Path(temp_dir) / repo_name
            
            logger.info(f"Cloning repository to {local_path}")
            
            # Clone with GitPython
            clone_url = f"https://{self.config.github.token}@github.com/{owner}/{repo_name}.git"
            repo = Repo.clone_from(clone_url, str(local_path))
            
            # Get default branch
            default_branch = repo_info.default_branch
            
            # Analyze repository structure
            structure = self._analyze_repository_structure(local_path)
            important_files = self._identify_important_files(local_path)
            
            # Get key file contents
            key_files_content = self._extract_key_file_contents(local_path, important_files)
            
            # Detect languages used
            languages = self._detect_languages(local_path)
            
            # Count files
            file_count = self._count_files(local_path)
            
            # Create context
            context = RepositoryContext(
                repo_url=repo_url,
                owner=owner,
                repo_name=repo_name,
                repo_info=repo_info,
                local_path=str(local_path),
                temp_dir=temp_dir,
                structure=structure,
                important_files=important_files,
                key_files_content=key_files_content,
                languages=languages,
                file_count=file_count,
                default_branch=default_branch
            )
            
            # Cache the context
            self.context_cache[cache_key] = context
            
            logger.info(f"Repository analysis complete: {file_count} files, languages: {languages}")
            
            return context
            
        except Exception as e:
            logger.error(f"Failed to analyze repository: {e}")
            raise
    
    def plan_edits(self, context: RepositoryContext, user_request: str) -> EditPlan:
        """
        Plan edits for a repository
        
        Args:
            context: Repository context
            user_request: User's editing request
            
        Returns:
            EditPlan object
        """
        logger.info(f"Planning edits for request: {user_request[:50]}...")
        
        try:
            # Generate edit plan using AI
            plan = self.ai_editor.generate_edit_plan(
                repo_context=context.to_dict(),
                user_request=user_request
            )
            
            logger.info(f"Edit plan generated: {len(plan.instructions)} instructions")
            logger.info(f"Estimated time: {plan.estimated_time}, Confidence: {plan.confidence}")
            
            # Validate plan
            self._validate_edit_plan(plan, context)
            
            return plan
            
        except Exception as e:
            logger.error(f"Failed to plan edits: {e}")
            raise
    
    def execute_edits(self, context: RepositoryContext, plan: EditPlan, 
                     user_request: str) -> EditResult:
        """
        Execute planned edits
        
        Args:
            context: Repository context
            plan: Edit plan
            user_request: Original user request
            
        Returns:
            EditResult object
        """
        logger.info(f"Executing {len(plan.instructions)} edit instructions")
        
        changes = []
        errors = []
        warnings = []
        
        # Process instructions in priority order
        sorted_instructions = sorted(plan.instructions, key=lambda x: x.priority)
        
        for instruction in sorted_instructions:
            try:
                file_path = instruction.file_path
                full_path = Path(context.local_path) / file_path
                
                logger.info(f"Processing {instruction.change_type} on {file_path}")
                
                if instruction.change_type == "modify":
                    if not full_path.exists():
                        warnings.append(f"File not found for modification: {file_path}")
                        continue
                    
                    # Read original content
                    with open(full_path, 'r', encoding='utf-8') as f:
                        original_content = f.read()
                    
                    # Determine language
                    language = self.analyzer.detect_language(file_path, original_content)
                    
                    # Generate new content
                    new_content = self.ai_editor.edit_file(
                        file_content=original_content,
                        file_path=file_path,
                        language=language,
                        instruction=instruction.description,
                        context=instruction.context
                    )
                    
                    # Validate the change
                    is_valid, validation_warnings = self.ai_editor.validate_edit(
                        original_content, new_content, file_path, language
                    )
                    
                    # Review the change
                    review_result = self.ai_editor.review_changes(
                        original_content, new_content, file_path, language
                    )
                    
                    # Generate explanation
                    explanation = self.ai_editor.explain_changes(
                        original_content, new_content, file_path, language, user_request
                    )
                    
                    # Create file change record
                    change = FileChange(
                        file_path=file_path,
                        original_content=original_content,
                        new_content=new_content,
                        change_type="modified",
                        language=language,
                        validation_result={
                            "valid": is_valid,
                            "warnings": validation_warnings
                        },
                        review_result=review_result,
                        explanation=explanation
                    )
                    
                    if is_valid:
                        # Write the change
                        with open(full_path, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        changes.append(change)
                        logger.info(f"Successfully modified {file_path}")
                    else:
                        errors.append(f"Validation failed for {file_path}: {validation_warnings}")
                
                elif instruction.change_type == "create":
                    # Create new file
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Determine language from file extension
                    language = self.analyzer.detect_language(file_path)
                    
                    # Generate content using AI (empty string as original)
                    new_content = self.ai_editor.edit_file(
                        file_content="",
                        file_path=file_path,
                        language=language,
                        instruction=instruction.description,
                        context=instruction.context
                    )
                    
                    # Write the file
                    with open(full_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    
                    # Create file change record
                    change = FileChange(
                        file_path=file_path,
                        original_content="",
                        new_content=new_content,
                        change_type="created",
                        language=language,
                        validation_result={"valid": True, "warnings": []}
                    )
                    
                    changes.append(change)
                    logger.info(f"Successfully created {file_path}")
                
                elif instruction.change_type == "delete":
                    if full_path.exists():
                        # Read original content for record
                        with open(full_path, 'r', encoding='utf-8') as f:
                            original_content = f.read()
                        
                        # Determine language
                        language = self.analyzer.detect_language(file_path, original_content)
                        
                        # Delete the file
                        full_path.unlink()
                        
                        # Create file change record
                        change = FileChange(
                            file_path=file_path,
                            original_content=original_content,
                            new_content="",
                            change_type="deleted",
                            language=language,
                            validation_result={"valid": True, "warnings": []}
                        )
                        
                        changes.append(change)
                        logger.info(f"Successfully deleted {file_path}")
                    else:
                        warnings.append(f"File not found for deletion: {file_path}")
                
                elif instruction.change_type == "rename":
                    # This is more complex - we'll implement it if needed
                    warnings.append(f"Rename operation not yet implemented: {file_path}")
            
            except Exception as e:
                error_msg = f"Failed to process instruction for {instruction.file_path}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        # Create summary
        summary = {
            "total_instructions": len(plan.instructions),
            "successful_changes": len(changes),
            "failed_changes": len(errors),
            "warnings_count": len(warnings),
            "files_modified": len([c for c in changes if c.change_type == "modified"]),
            "files_created": len([c for c in changes if c.change_type == "created"]),
            "files_deleted": len([c for c in changes if c.change_type == "deleted"]),
            "timestamp": datetime.now().isoformat()
        }
        
        success = len(changes) > 0 and len(errors) == 0
        
        return EditResult(
            success=success,
            changes=changes,
            plan=plan,
            summary=summary,
            errors=errors,
            warnings=warnings
        )
    
    def create_pull_request(self, context: RepositoryContext, edit_result: EditResult,
                           branch_name: str, pr_title: str, pr_body: str) -> Dict[str, Any]:
        """
        Create a pull request with the changes
        
        Args:
            context: Repository context
            edit_result: Edit result
            branch_name: Branch name
            pr_title: PR title
            pr_body: PR description
            
        Returns:
            PR creation result
        """
        logger.info(f"Creating pull request for branch: {branch_name}")
        
        try:
            # Create branch
            branch_result = self.github.create_branch(
                context.owner,
                context.repo_name,
                branch_name,
                context.default_branch
            )
            
            # Commit and push changes
            self._commit_and_push_changes(context, edit_result, branch_name)
            
            # Create pull request
            pr = self.github.create_pull_request(
                context.owner,
                context.repo_name,
                title=pr_title,
                body=pr_body,
                head=branch_name,
                base=context.default_branch
            )
            
            # Update edit result
            edit_result.branch_name = branch_name
            edit_result.pr_url = pr.get('html_url')
            
            return {
                "success": True,
                "pull_request_url": pr.get('html_url'),
                "branch": branch_name,
                "pr_number": pr.get('number'),
                "title": pr.get('title'),
                "body": pr.get('body')
            }
            
        except Exception as e:
            logger.error(f"Failed to create pull request: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def cleanup(self, context: RepositoryContext):
        """
        Clean up temporary files
        
        Args:
            context: Repository context
        """
        if context.temp_dir and os.path.exists(context.temp_dir):
            try:
                shutil.rmtree(context.temp_dir)
                logger.info(f"Cleaned up temp directory: {context.temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp directory: {e}")
    
    def _analyze_repository_structure(self, local_path: Path) -> Dict[str, Any]:
        """
        Analyze repository directory structure
        
        Args:
            local_path: Local repository path
            
        Returns:
            Nested directory structure
        """
        structure = {}
        
        def analyze_dir(path: Path, depth: int = 0) -> Dict:
            """Recursively analyze directory"""
            if depth > 5:  # Limit recursion depth
                return {"type": "directory", "truncated": True}
            
            result = {}
            for item in path.iterdir():
                if item.is_dir():
                    # Skip common ignored directories
                    if item.name in ['.git', '__pycache__', 'node_modules', '.venv', 'venv', 'env', '.env']:
                        continue
                    
                    result[item.name] = analyze_dir(item, depth + 1)
                else:
                    # Check if file extension is allowed
                    ext = item.suffix.lower()
                    if ext in self.config.file.allowed_extensions:
                        result[item.name] = {
                            "type": "file",
                            "size": item.stat().st_size,
                            "language": self.analyzer.detect_language(item.name)
                        }
            
            return result
        
        structure = analyze_dir(local_path)
        return structure
    
    def _identify_important_files(self, local_path: Path) -> List[str]:
        """
        Identify important configuration and source files
        
        Args:
            local_path: Local repository path
            
        Returns:
            List of important file paths
        """
        important_patterns = [
            'README*', 'CONTRIBUTING*', 'LICENSE*', 'CHANGELOG*',
            'package.json', 'requirements.txt', 'pyproject.toml',
            'setup.py', 'setup.cfg', 'Pipfile', 'poetry.lock',
            'Dockerfile', 'docker-compose.yml', '.dockerignore',
            '.gitignore', '.env*', '.env.example',
            'Makefile', 'CMakeLists.txt',
            '*.py', '*.js', '*.ts', '*.jsx', '*.tsx',
            'src/', 'lib/', 'app/', 'main.py', 'app.py', 'index.js',
            '*.yml', '*.yaml', '*.json', '*.xml'
        ]
        
        important_files = []
        
        for pattern in important_patterns:
            if pattern.endswith('/'):
                # Directory pattern
                dir_name = pattern.rstrip('/')
                dir_path = local_path / dir_name
                if dir_path.exists() and dir_path.is_dir():
                    # Add all files in directory
                    for file in dir_path.rglob('*'):
                        if file.is_file() and file.suffix.lower() in self.config.file.allowed_extensions:
                            rel_path = file.relative_to(local_path)
                            important_files.append(str(rel_path))
            else:
                # File pattern
                for file in local_path.rglob(pattern):
                    if file.is_file() and file.suffix.lower() in self.config.file.allowed_extensions:
                        rel_path = file.relative_to(local_path)
                        important_files.append(str(rel_path))
        
        # Deduplicate and limit
        important_files = list(set(important_files))[:50]  # Limit to 50 files
        
        return important_files
    
    def _extract_key_file_contents(self, local_path: Path, important_files: List[str]) -> Dict[str, str]:
        """
        Extract content of key files for AI context
        
        Args:
            local_path: Local repository path
            important_files: List of important file paths
            
        Returns:
            Dictionary of file paths to content snippets
        """
        key_contents = {}
        
        for file_path in important_files[:10]:  # Limit to 10 files
            full_path = local_path / file_path
            if full_path.exists():
                try:
                    # Read file with size limit
                    file_size = full_path.stat().st_size
                    if file_size > self.config.file.max_file_size_bytes:
                        continue
                    
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Limit content length
                    if len(content) > 5000:
                        content = content[:5000] + "\n... [truncated]"
                    
                    key_contents[file_path] = content
                except Exception as e:
                    logger.warning(f"Failed to read file {file_path}: {e}")
        
        return key_contents
    
    def _detect_languages(self, local_path: Path) -> List[str]:
        """
        Detect programming languages used in repository
        
        Args:
            local_path: Local repository path
            
        Returns:
            List of languages detected
        """
        languages = set()
        
        for file in local_path.rglob('*'):
            if file.is_file():
                language = self.analyzer.detect_language(file.name)
                if language != 'unknown':
                    languages.add(language)
        
        return sorted(list(languages))
    
    def _count_files(self, local_path: Path) -> int:
        """
        Count total files in repository (excluding ignored directories)
        
        Args:
            local_path: Local repository path
            
        Returns:
            File count
        """
        count = 0
        ignore_dirs = ['.git', '__pycache__', 'node_modules', '.venv', 'venv', 'env']
        
        for file in local_path.rglob('*'):
            if file.is_file():
                # Check if any ignored directory is in path
                if not any(ignore_dir in str(file) for ignore_dir in ignore_dirs):
                    count += 1
        
        return count
    
    def _validate_edit_plan(self, plan: EditPlan, context: RepositoryContext):
        """
        Validate edit plan for safety and feasibility
        
        Args:
            plan: Edit plan
            context: Repository context
        """
        warnings = []
        
        # Check for too many changes
        if len(plan.instructions) > 20:
            warnings.append(f"Plan has {len(plan.instructions)} instructions, which is a lot")
        
        # Check for risky operations
        for instruction in plan.instructions:
            file_path = instruction.file_path
            
            # Check for system files
            risky_patterns = [
                r'\.git/',
                r'/etc/',
                r'/bin/',
                r'/usr/',
                r'/var/',
                r'/sys/',
                r'/proc/'
            ]
            
            for pattern in risky_patterns:
                if re.search(pattern, file_path):
                    warnings.append(f"Risky file path: {file_path}")
            
            # Check for deletion of important files
            if instruction.change_type == "delete":
                important_extensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs']
                if any(file_path.endswith(ext) for ext in important_extensions):
                    warnings.append(f"Deleting source code file: {file_path}")
        
        # Log warnings
        if warnings:
            logger.warning(f"Edit plan validation warnings: {warnings}")
    
    def _commit_and_push_changes(self, context: RepositoryContext, 
                                edit_result: EditResult, branch_name: str):
        """
        Commit and push changes to GitHub
        
        Args:
            context: Repository context
            edit_result: Edit result
            branch_name: Branch name
        """
        local_path = Path(context.local_path)
        
        # Initialize git repo
        repo = Repo(local_path)
        
        # Create or switch to branch
        try:
            # Check if branch exists locally
            if branch_name in repo.heads:
                branch = repo.heads[branch_name]
                branch.checkout()
            else:
                # Create new branch
                branch = repo.create_head(branch_name)
                branch.checkout()
        except GitCommandError as e:
            logger.error(f"Failed to checkout branch {branch_name}: {e}")
            raise
        
        # Stage all changes
        repo.git.add(A=True)
        
        # Check if there are changes to commit
        if not repo.is_dirty():
            logger.warning("No changes to commit")
            return
        
        # Create commit message
        commit_message = self._generate_commit_message(edit_result)
        
        # Commit changes
        repo.index.commit(commit_message)
        
        # Push to remote
        try:
            origin = repo.remote(name='origin')
            push_result = origin.push(branch_name, force=True)
            logger.info(f"Pushed changes to branch {branch_name}")
        except GitCommandError as e:
            logger.error(f"Failed to push changes: {e}")
            raise
    
    def _generate_commit_message(self, edit_result: EditResult) -> str:
        """
        Generate commit message from edit result
        
        Args:
            edit_result: Edit result
            
        Returns:
            Commit message
        """
        # Count changes by type
        modified = len([c for c in edit_result.changes if c.change_type == "modified"])
        created = len([c for c in edit_result.changes if c.change_type == "created"])
        deleted = len([c for c in edit_result.changes if c.change_type == "deleted"])
        
        # Create summary
        summary_parts = []
        if modified > 0:
            summary_parts.append(f"{modified} modified")
        if created > 0:
            summary_parts.append(f"{created} created")
        if deleted > 0:
            summary_parts.append(f"{deleted} deleted")
        
        summary = ", ".join(summary_parts)
        
        # Main commit message
        message = f"AI-generated edits: {summary}\n\n"
        
        # Add file list (truncated)
        file_list = []
        for change in edit_result.changes[:5]:  # First 5 files
            action = {
                "modified": "M",
                "created": "A",
                "deleted": "D"
            }.get(change.change_type, "?")
            file_list.append(f"{action} {change.file_path}")
        
        if file_list:
            message += "Files changed:\n" + "\n".join(file_list)
        
        if len(edit_result.changes) > 5:
            message += f"\n... and {len(edit_result.changes) - 5} more files"
        
        return message
    
    def generate_branch_name(self, user_request: str) -> str:
        """
        Generate a branch name from user request
        
        Args:
            user_request: User's editing request
            
        Returns:
            Branch name
        """
        # Clean the request
        clean_request = re.sub(r'[^a-zA-Z0-9\s-]', '', user_request)
        clean_request = clean_request.strip().lower()
        
        # Take first few words
        words = clean_request.split()[:4]
        
        # Join with hyphens and truncate
        branch_name = "ai-edit-" + "-".join(words)
        branch_name = branch_name[:50]  # GitHub branch name limit
        
        # Add timestamp for uniqueness
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        branch_name = f"{branch_name}-{timestamp}"
        
        return branch_name
    
    def generate_pr_details(self, user_request: str, edit_result: EditResult) -> Tuple[str, str]:
        """
        Generate PR title and description
        
        Args:
            user_request: User's editing request
            edit_result: Edit result
            
        Returns:
            Tuple of (title, description)
        """
        # PR title
        title = f"AI Edit: {user_request[:50]}"
        if len(user_request) > 50:
            title += "..."
        
        # PR description
        description = f"## AI-Generated Changes\n\n"
        description += f"**Original Request:** {user_request}\n\n"
        
        # Summary
        description += "### Summary\n\n"
        description += f"- Total changes: {len(edit_result.changes)} files\n"
        
        modified = len([c for c in edit_result.changes if c.change_type == "modified"])
        created = len([c for c in edit_result.changes if c.change_type == "created"])
        deleted = len([c for c in edit_result.changes if c.change_type == "deleted"])
        
        if modified > 0:
            description += f"- Modified: {modified} files\n"
        if created > 0:
            description += f"- Created: {created} files\n"
        if deleted > 0:
            description += f"- Deleted: {deleted} files\n"
        
        # File list
        description += "\n### Changed Files\n\n"
        for change in edit_result.changes[:10]:  # First 10 files
            emoji = {
                "modified": "📝",
                "created": "✨",
                "deleted": "🗑️"
            }.get(change.change_type, "❓")
            
            description += f"{emoji} `{change.file_path}` ({change.change_type})\n"
        
        if len(edit_result.changes) > 10:
            description += f"\n... and {len(edit_result.changes) - 10} more files\n"
        
        # AI Review section
        description += "\n### AI Review Summary\n\n"
        
        # Count issues by severity
        critical_issues = 0
        high_issues = 0
        medium_issues = 0
        
        for change in edit_result.changes:
            if change.review_result and 'issues' in change.review_result:
                for issue in change.review_result['issues']:
                    if issue.get('severity') == 'critical':
                        critical_issues += 1
                    elif issue.get('severity') == 'high':
                        high_issues += 1
                    elif issue.get('severity') == 'medium':
                        medium_issues += 1
        
        if critical_issues > 0:
            description += f"⚠️ **Critical Issues:** {critical_issues}\n"
        if high_issues > 0:
            description += f"⚠️ **High Issues:** {high_issues}\n"
        if medium_issues > 0:
            description += f"ℹ️ **Medium Issues:** {medium_issues}\n"
        
        if critical_issues == 0 and high_issues == 0 and medium_issues == 0:
            description += "✅ No major issues detected by AI review\n"
        
        # Footer
        description += "\n---\n"
        description += "*This pull request was automatically generated by GitHub AI Editor.*\n"
        description += "*Please review the changes carefully before merging.*\n"
        
        return title, description
