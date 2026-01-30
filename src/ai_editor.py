"""
AI-powered code editing using OpenAI's API
"""

import json
import re
from typing import Dict, List, Optional, Any, Tuple
import openai
from openai import OpenAI
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class EditInstruction:
    """Represents an edit instruction"""
    file_path: str
    change_type: str  # "modify", "create", "delete", "rename"
    description: str
    context: Optional[Dict[str, Any]] = None
    priority: int = 1  # 1-5, higher is more important

@dataclass
class EditPlan:
    """Represents a complete edit plan"""
    instructions: List[EditInstruction]
    dependencies: List[str]
    risks: List[str]
    estimated_time: str  # "quick", "medium", "complex"
    confidence: float  # 0-1

class AIEditor:
    """AI-powered code editor using OpenAI"""
    
    def __init__(self, api_key: str, model: str = "gpt-4", max_tokens: int = 4000, temperature: float = 0.1):
        """
        Initialize AI editor
        
        Args:
            api_key: OpenAI API key
            model: Model to use
            max_tokens: Maximum tokens in response
            temperature: Creativity temperature (0-1)
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        
        # System prompts for different tasks
        self.system_prompts = {
            "analyze": """You are an expert software engineer and architect. 
            Analyze the repository structure and user request to understand what needs to be changed.
            Consider code architecture, dependencies, best practices, and potential side effects.""",
            
            "plan": """You are a senior software engineer creating an edit plan.
            Create a detailed, step-by-step plan for making the requested changes.
            Consider:
            1. Which files need to be modified, created, or deleted
            2. The order of changes (dependencies between files)
            3. Potential risks and how to mitigate them
            4. Testing requirements
            5. Best practices for the specific language/framework""",
            
            "edit": """You are a meticulous code editor. 
            Make the requested changes to the code while preserving:
            1. Existing formatting style
            2. Comments and documentation
            3. Code structure and organization
            4. Variable naming conventions
            Only make the changes that are explicitly requested or required by those changes.""",
            
            "review": """You are a code reviewer checking changes for:
            1. Syntax correctness
            2. Logical errors
            3. Security issues
            4. Performance problems
            5. Style consistency
            6. Missing edge cases""",
            
            "explain": """You are a teacher explaining code changes.
            Explain what was changed and why in clear, simple terms.
            Focus on the reasoning behind changes and their implications."""
        }
    
    def generate_edit_plan(self, repo_context: Dict[str, Any], user_request: str) -> EditPlan:
        """
        Generate a detailed edit plan
        
        Args:
            repo_context: Repository context (structure, files, etc.)
            user_request: User's editing request
            
        Returns:
            EditPlan object
        """
        logger.info(f"Generating edit plan for request: {user_request[:50]}...")
        
        # Prepare context for the AI
        context = self._prepare_repo_context(repo_context)
        
        messages = [
            {"role": "system", "content": self.system_prompts["plan"]},
            {"role": "user", "content": self._create_plan_prompt(context, user_request)}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"}
            )
            
            plan_data = json.loads(response.choices[0].message.content)
            
            # Convert to EditPlan object
            instructions = [
                EditInstruction(
                    file_path=instr.get("file_path"),
                    change_type=instr.get("change_type", "modify"),
                    description=instr.get("description", ""),
                    context=instr.get("context"),
                    priority=instr.get("priority", 1)
                )
                for instr in plan_data.get("instructions", [])
            ]
            
            return EditPlan(
                instructions=instructions,
                dependencies=plan_data.get("dependencies", []),
                risks=plan_data.get("risks", []),
                estimated_time=plan_data.get("estimated_time", "medium"),
                confidence=plan_data.get("confidence", 0.7)
            )
            
        except Exception as e:
            logger.error(f"Failed to generate edit plan: {e}")
            raise
    
    def edit_file(self, file_content: str, file_path: str, language: str, 
                 instruction: str, context: Optional[Dict] = None) -> str:
        """
        Edit a single file based on instruction
        
        Args:
            file_content: Current file content
            file_path: Path to the file
            language: Programming language
            instruction: What to change
            context: Additional context about the file
            
        Returns:
            Edited file content
        """
        logger.info(f"Editing file: {file_path}")
        
        messages = [
            {"role": "system", "content": self.system_prompts["edit"]},
            {"role": "user", "content": self._create_edit_prompt(
                file_content, file_path, language, instruction, context
            )}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=min(self.max_tokens, len(file_content) + 1000)
            )
            
            edited_content = response.choices[0].message.content
            
            # Clean up the response (remove markdown code blocks if present)
            edited_content = self._clean_ai_response(edited_content, language)
            
            return edited_content
            
        except Exception as e:
            logger.error(f"Failed to edit file {file_path}: {e}")
            raise
    
    def review_changes(self, original: str, modified: str, file_path: str, 
                      language: str) -> Dict[str, Any]:
        """
        Review changes for quality and safety
        
        Args:
            original: Original file content
            modified: Modified file content
            file_path: Path to the file
            language: Programming language
            
        Returns:
            Review results
        """
        if original == modified:
            return {"status": "unchanged", "issues": []}
        
        messages = [
            {"role": "system", "content": self.system_prompts["review"]},
            {"role": "user", "content": self._create_review_prompt(
                original, modified, file_path, language
            )}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,  # Low temperature for consistent reviews
                max_tokens=1000
            )
            
            review_text = response.choices[0].message.content
            
            # Parse review results
            issues = self._parse_review(review_text)
            
            return {
                "status": "reviewed",
                "issues": issues,
                "summary": review_text[:500]  # First 500 chars as summary
            }
            
        except Exception as e:
            logger.error(f"Failed to review changes for {file_path}: {e}")
            return {"status": "error", "error": str(e), "issues": []}
    
    def explain_changes(self, original: str, modified: str, file_path: str, 
                       language: str, user_request: str) -> str:
        """
        Generate explanation for changes
        
        Args:
            original: Original file content
            modified: Modified file content
            file_path: Path to the file
            language: Programming language
            user_request: Original user request
            
        Returns:
            Explanation text
        """
        if original == modified:
            return "No changes were made to this file."
        
        messages = [
            {"role": "system", "content": self.system_prompts["explain"]},
            {"role": "user", "content": self._create_explanation_prompt(
                original, modified, file_path, language, user_request
            )}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=800
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Failed to explain changes for {file_path}: {e}")
            return f"Changes were made to {file_path}, but an error occurred while generating explanation: {str(e)}"
    
    def _prepare_repo_context(self, repo_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare repository context for AI prompts
        
        Args:
            repo_context: Raw repository context
            
        Returns:
            Prepared context
        """
        # Extract key information
        context = {
            "repository": {
                "owner": repo_context.get("owner"),
                "name": repo_context.get("repo"),
                "description": repo_context.get("description", ""),
                "default_branch": repo_context.get("default_branch", "main")
            },
            "structure": repo_context.get("structure", {}),
            "important_files": repo_context.get("important_files", []),
            "languages": repo_context.get("languages", []),
            "file_count": repo_context.get("file_count", 0)
        }
        
        # Add sample content for key files
        key_files = repo_context.get("key_files", {})
        if key_files:
            context["key_files"] = {}
            for file_path, content in list(key_files.items())[:5]:  # Limit to 5 files
                context["key_files"][file_path] = content[:1000]  # First 1000 chars
        
        return context
    
    def _create_plan_prompt(self, context: Dict[str, Any], user_request: str) -> str:
        """
        Create prompt for edit planning
        
        Args:
            context: Repository context
            user_request: User's editing request
            
        Returns:
            Formatted prompt
        """
        return f"""
# Repository Context
{json.dumps(context, indent=2, ensure_ascii=False)}

# User Request
{user_request}

# Task
Create a detailed edit plan to fulfill the user request.

# Output Format
Return JSON with the following structure:
{{
  "instructions": [
    {{
      "file_path": "path/to/file.py",
      "change_type": "modify|create|delete|rename",
      "description": "Detailed description of what to change",
      "priority": 1,
      "context": {{}}
    }}
  ],
  "dependencies": ["List of dependencies to consider"],
  "risks": ["List of potential risks"],
  "estimated_time": "quick|medium|complex",
  "confidence": 0.8
}}

# Guidelines
1. Be specific about file paths and changes
2. Consider dependencies between files
3. Note potential breaking changes
4. Suggest testing if needed
5. Order changes by priority (1 = must do first, 5 = can do last)

Now, create the edit plan:
"""
    
    def _create_edit_prompt(self, file_content: str, file_path: str, 
                           language: str, instruction: str, context: Optional[Dict]) -> str:
        """
        Create prompt for editing a file
        
        Args:
            file_content: Current file content
            file_path: Path to file
            language: Programming language
            instruction: What to change
            context: Additional context
            
        Returns:
            Formatted prompt
        """
        context_str = ""
        if context:
            context_str = f"\n# Additional Context\n{json.dumps(context, indent=2)}"
        
        return f"""
# File Information
- Path: {file_path}
- Language: {language}

# Current File Content
