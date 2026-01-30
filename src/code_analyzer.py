"""
Code analysis utilities for understanding and validating code
"""

import ast
import json
import re
from typing import Dict, List, Optional, Tuple, Any, Set
import subprocess
import tempfile
import os
from pathlib import Path
import logging
import hashlib

logger = logging.getLogger(__name__)

class CodeAnalyzer:
    """Analyzes code structure, dependencies, and quality"""
    
    # Language-specific file extensions
    LANGUAGE_EXTENSIONS = {
        '.py': 'python',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.java': 'java',
        '.cpp': 'cpp',
        '.c': 'c',
        '.cs': 'csharp',
        '.go': 'go',
        '.rs': 'rust',
        '.rb': 'ruby',
        '.php': 'php',
        '.swift': 'swift',
        '.kt': 'kotlin',
        '.scala': 'scala',
        '.r': 'r',
        '.m': 'matlab',
        '.sql': 'sql',
        '.sh': 'shell',
        '.bash': 'shell',
        '.ps1': 'powershell',
        '.html': 'html',
        '.css': 'css',
        '.scss': 'scss',
        '.sass': 'sass',
        '.less': 'less',
        '.json': 'json',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.xml': 'xml',
        '.md': 'markdown',
        '.txt': 'text',
        '.dockerfile': 'dockerfile',
        '.gitignore': 'gitignore',
        '.env': 'env',
    }
    
    @staticmethod
    def detect_language(filename: str, content: Optional[str] = None) -> str:
        """
        Detect programming language from filename and optionally content
        
        Args:
            filename: Name of the file
            content: File content (optional)
            
        Returns:
            Language name
        """
        # Try by extension first
        ext = Path(filename).suffix.lower()
        if ext in CodeAnalyzer.LANGUAGE_EXTENSIONS:
            return CodeAnalyzer.LANGUAGE_EXTENSIONS[ext]
        
        # Try by shebang if content provided
        if content:
            first_line = content.split('\n')[0].strip()
            shebang_mapping = {
                'python': ['python', 'python2', 'python3'],
                'bash': ['bash', 'sh'],
                'node': ['node'],
                'ruby': ['ruby'],
                'perl': ['perl'],
                'php': ['php'],
            }
            
            if first_line.startswith('#!'):
                for lang, interpreters in shebang_mapping.items():
                    if any(interpreter in first_line for interpreter in interpreters):
                        return lang
        
        # Try by filename patterns
        filename_lower = filename.lower()
        if 'dockerfile' in filename_lower:
            return 'dockerfile'
        elif 'makefile' in filename_lower:
            return 'makefile'
        elif filename_lower == '.gitignore':
            return 'gitignore'
        elif filename_lower == '.env':
            return 'env'
        
        return 'unknown'
    
    @staticmethod
    def analyze_python_code(content: str) -> Dict[str, Any]:
        """
        Analyze Python code structure
        
        Args:
            content: Python code content
            
        Returns:
            Analysis dictionary
        """
        analysis = {
            "valid": False,
            "syntax_error": None,
            "imports": [],
            "functions": [],
            "classes": [],
            "docstrings": [],
            "line_count": 0,
            "complexity": 0,
            "dependencies": []
        }
        
        try:
            # Parse AST
            tree = ast.parse(content)
            
            # Basic statistics
            analysis["line_count"] = len(content.split('\n'))
            analysis["valid"] = True
            
            # Extract information
            for node in ast.walk(tree):
                # Imports
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        analysis["imports"].append({
                            "module": alias.name,
                            "alias": alias.asname,
                            "type": "import"
                        })
                        if alias.name not in analysis["dependencies"]:
                            analysis["dependencies"].append(alias.name)
                
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        full_name = f"{module}.{alias.name}" if module else alias.name
                        analysis["imports"].append({
                            "module": module,
                            "name": alias.name,
                            "alias": alias.asname,
                            "type": "from_import"
                        })
                        if module and module not in analysis["dependencies"]:
                            analysis["dependencies"].append(module)
                
                # Functions
                elif isinstance(node, ast.FunctionDef):
                    func_info = {
                        "name": node.name,
                        "args": len(node.args.args),
                        "lineno": node.lineno,
                        "docstring": ast.get_docstring(node)
                    }
                    analysis["functions"].append(func_info)
                
                # Classes
                elif isinstance(node, ast.ClassDef):
                    class_info = {
                        "name": node.name,
                        "bases": [base.id for base in node.bases if isinstance(base, ast.Name)],
                        "lineno": node.lineno,
                        "docstring": ast.get_docstring(node)
                    }
                    analysis["classes"].append(class_info)
                
                # Docstrings
                if hasattr(node, 'body') and node.body:
                    first_node = node.body[0]
                    if isinstance(first_node, ast.Expr) and isinstance(first_node.value, ast.Constant):
                        if isinstance(first_node.value.value, str):
                            analysis["docstrings"].append(first_node.value.value[:100])
            
            # Calculate rough complexity (function count + class count)
            analysis["complexity"] = len(analysis["functions"]) + len(analysis["classes"])
            
        except SyntaxError as e:
            analysis["syntax_error"] = {
                "message": str(e),
                "lineno": e.lineno,
                "offset": e.offset
            }
        except Exception as e:
            analysis["syntax_error"] = {
                "message": str(e)
            }
        
        return analysis
    
    @staticmethod
    def analyze_javascript_code(content: str) -> Dict[str, Any]:
        """
        Analyze JavaScript/TypeScript code structure
        
        Args:
            content: JavaScript/TypeScript code
            
        Returns:
            Analysis dictionary
        """
        analysis = {
            "valid": True,  # We'll assume valid since parsing JS is complex
            "imports": [],
            "exports": [],
            "functions": [],
            "classes": [],
            "line_count": len(content.split('\n')),
            "dependencies": []
        }
        
        # Extract imports (ES6 and CommonJS)
        import_patterns = [
            r"import\s+(?:(?:\*\s+as\s+(\w+))|(?:{[^}]+})|(?:(\w+)))\s+from\s+['\"]([^'\"]+)['\"]",
            r"require\(['\"]([^'\"]+)['\"]\)",
            r"import\s+['\"]([^'\"]+)['\"]"
        ]
        
        for pattern in import_patterns:
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                if match.lastindex:
                    module = match.group(match.lastindex)
                    analysis["imports"].append({
                        "module": module,
                        "line": content[:match.start()].count('\n') + 1
                    })
                    if module not in analysis["dependencies"]:
                        analysis["dependencies"].append(module)
        
        # Extract function declarations
        func_patterns = [
            r"(?:function\s+(\w+)\s*\([^)]*\))|(?:const\s+(\w+)\s*=\s*(?:\([^)]*\)\s*=>|function))|(?:let\s+(\w+)\s*=\s*(?:\([^)]*\)\s*=>|function))|(?:var\s+(\w+)\s*=\s*(?:\([^)]*\)\s*=>|function))"
        ]
        
        for pattern in func_patterns:
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                for i in range(1, len(match.groups()) + 1):
                    if match.group(i):
                        analysis["functions"].append({
                            "name": match.group(i),
                            "line": content[:match.start()].count('\n') + 1
                        })
                        break
        
        # Extract class declarations
        class_pattern = r"class\s+(\w+)"
        matches = re.finditer(class_pattern, content, re.MULTILINE)
        for match in matches:
            analysis["classes"].append({
                "name": match.group(1),
                "line": content[:match.start()].count('\n') + 1
            })
        
        return analysis
    
    @staticmethod
    def analyze_json_code(content: str) -> Dict[str, Any]:
        """
        Analyze JSON content
        
        Args:
            content: JSON content
            
        Returns:
            Analysis dictionary
        """
        analysis = {
            "valid": False,
            "syntax_error": None,
            "size": 0,
            "is_array": False,
            "key_count": 0
        }
        
        try:
            data = json.loads(content)
            analysis["valid"] = True
            analysis["size"] = len(content)
            
            if isinstance(data, dict):
                analysis["key_count"] = len(data.keys())
            elif isinstance(data, list):
                analysis["is_array"] = True
                analysis["key_count"] = len(data)
            
        except json.JSONDecodeError as e:
            analysis["syntax_error"] = {
                "message": str(e),
                "lineno": e.lineno,
                "colno": e.colno
            }
        
        return analysis
    
    @staticmethod
    def analyze_markdown(content: str) -> Dict[str, Any]:
        """
        Analyze Markdown content
        
        Args:
            content: Markdown content
            
        Returns:
            Analysis dictionary
        """
        analysis = {
            "headings": [],
            "code_blocks": [],
            "links": [],
            "images": [],
            "line_count": len(content.split('\n')),
            "word_count": len(content.split())
        }
        
        # Extract headings
        heading_pattern = r"^(#{1,6})\s+(.+)$"
        matches = re.finditer(heading_pattern, content, re.MULTILINE)
        for match in matches:
            analysis["headings"].append({
                "level": len(match.group(1)),
                "text": match.group(2).strip(),
                "line": content[:match.start()].count('\n') + 1
            })
        
        # Extract code blocks
        code_pattern = r"```([\w]*)\n(.*?)```"
        matches = re.finditer(code_pattern, content, re.MULTILINE | re.DOTALL)
        for match in matches:
            analysis["code_blocks"].append({
                "language": match.group(1) or "unknown",
                "line": content[:match.start()].count('\n') + 1,
                "size": len(match.group(2))
            })
        
        # Extract links
        link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
        matches = re.finditer(link_pattern, content)
        for match in matches:
            analysis["links"].append({
                "text": match.group(1),
                "url": match.group(2)
            })
        
        return analysis
    
    @staticmethod
    def analyze_code(content: str, language: str) -> Dict[str, Any]:
        """
        Analyze code based on language
        
        Args:
            content: Code content
            language: Programming language
            
        Returns:
            Analysis dictionary
        """
        if language == "python":
            return CodeAnalyzer.analyze_python_code(content)
        elif language in ["javascript", "typescript"]:
            return CodeAnalyzer.analyze_javascript_code(content)
        elif language == "json":
            return CodeAnalyzer.analyze_json_code(content)
        elif language == "markdown":
            return CodeAnalyzer.analyze_markdown(content)
        else:
            # Generic analysis for other languages
            return {
                "valid": True,
                "line_count": len(content.split('\n')),
                "size": len(content),
                "language": language
            }
    
    @staticmethod
    def validate_python_syntax(content: str) -> Tuple[bool, Optional[str]]:
        """
        Validate Python syntax
        
        Args:
            content: Python code
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            ast.parse(content)
            return True, None
        except SyntaxError as e:
            return False, f"Syntax error at line {e.lineno}: {e.msg}"
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def validate_json_syntax(content: str) -> Tuple[bool, Optional[str]]:
        """
        Validate JSON syntax
        
        Args:
            content: JSON content
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            json.loads(content)
            return True, None
        except json.JSONDecodeError as e:
            return False, f"JSON error at line {e.lineno}: {e.msg}"
    
    @staticmethod
    def validate_yaml_syntax(content: str) -> Tuple[bool, Optional[str]]:
        """
        Validate YAML syntax
        
        Args:
            content: YAML content
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            import yaml
            yaml.safe_load(content)
            return True, None
        except ImportError:
            # If pyyaml is not installed, skip validation
            return True, None
        except yaml.YAMLError as e:
            return False, str(e)
    
    @staticmethod
    def validate_syntax(content: str, language: str) -> Tuple[bool, Optional[str]]:
        """
        Validate syntax based on language
        
        Args:
            content: Code content
            language: Programming language
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if language == "python":
            return CodeAnalyzer.validate_python_syntax(content)
        elif language == "json":
            return CodeAnalyzer.validate_json_syntax(content)
        elif language == "yaml":
            return CodeAnalyzer.validate_yaml_syntax(content)
        else:
            # For other languages, we can't validate easily
            return True, None
    
    @staticmethod
    def get_file_dependencies(content: str, language: str) -> List[str]:
        """
        Extract dependencies from file content
        
        Args:
            content: File content
            language: Programming language
            
        Returns:
            List of dependencies
        """
        dependencies = []
        
        if language == "python":
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            dependencies.append(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            dependencies.append(node.module)
            except SyntaxError:
                pass
        
        elif language in ["javascript", "typescript"]:
            # Look for import/require statements
            patterns = [
                r"from\s+['\"]([^'\"]+)['\"]",
                r"import\s+['\"]([^'\"]+)['\"]",
                r"require\(['\"]([^'\"]+)['\"]\)"
            ]
            for pattern in patterns:
                matches = re.findall(pattern, content)
                dependencies.extend(matches)
        
        elif language in ["java", "c", "cpp", "csharp"]:
            # Look for #include or import statements
            patterns = [
                r'#include\s+[<"]([^>"]+)[>"]',
                r'import\s+([\w.]+);'
            ]
            for pattern in patterns:
                matches = re.findall(pattern, content)
                dependencies.extend(matches)
        
        return list(set(dependencies))  # Remove duplicates
    
    @staticmethod
    def calculate_complexity(content: str, language: str) -> int:
        """
        Calculate code complexity (simplified)
        
        Args:
            content: Code content
            language: Programming language
            
        Returns:
            Complexity score
        """
        if language == "python":
            try:
                tree = ast.parse(content)
                complexity = 0
                
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.If, ast.For, ast.While)):
                        complexity += 1
                    elif isinstance(node, ast.Try):
                        complexity += 2  # Try blocks are complex
                
                return complexity
            except SyntaxError:
                return 0
        
        # For other languages, use simple metrics
        complexity = 0
        
        # Count function-like definitions
        if language in ["javascript", "typescript"]:
            patterns = [
                r"function\s+\w+",
                r"class\s+\w+",
                r"const\s+\w+\s*=\s*(?:\([^)]*\)\s*=>|function)",
                r"let\s+\w+\s*=\s*(?:\([^)]*\)\s*=>|function)",
                r"var\s+\w+\s*=\s*(?:\([^)]*\)\s*=>|function)"
            ]
            for pattern in patterns:
                complexity += len(re.findall(pattern, content))
        
        # Count control structures
        control_patterns = [r"\bif\b", r"\bfor\b", r"\bwhile\b", r"\btry\b", r"\bcatch\b", r"\bswitch\b"]
        for pattern in control_patterns:
            complexity += len(re.findall(pattern, content, re.IGNORECASE))
        
        return complexity
    
    @staticmethod
    def compare_files(old_content: str, new_content: str) -> Dict[str, Any]:
        """
        Compare two versions of a file
        
        Args:
            old_content: Original content
            new_content: New content
            
        Returns:
            Comparison results
        """
        if old_content == new_content:
            return {
                "changed": False,
                "additions": 0,
                "deletions": 0,
                "similarity": 1.0
            }
        
        # Simple line-based comparison
        old_lines = old_content.split('\n')
        new_lines = new_content.split('\n')
        
        added = set(new_lines) - set(old_lines)
        removed = set(old_lines) - set(new_lines)
        
        # Calculate similarity using difflib
        import difflib
        similarity = difflib.SequenceMatcher(
            None, 
            old_content.split(), 
            new_content.split()
        ).ratio()
        
        return {
            "changed": True,
            "additions": len(added),
            "deletions": len(removed),
            "similarity": similarity,
            "added_lines": list(added)[:10],  # Limit for response size
            "removed_lines": list(removed)[:10]
        }
    
    @staticmethod
    def generate_file_summary(filename: str, content: str, language: str) -> Dict[str, Any]:
        """
        Generate comprehensive file summary
        
        Args:
            filename: File name
            content: File content
            language: Programming language
            
        Returns:
            File summary
        """
        analysis = CodeAnalyzer.analyze_code(content, language)
        
        summary = {
            "filename": filename,
            "language": language,
            "size_bytes": len(content.encode('utf-8')),
            "size_lines": len(content.split('\n')),
            "size_words": len(content.split()),
            "analysis": analysis,
            "dependencies": CodeAnalyzer.get_file_dependencies(content, language),
            "complexity": CodeAnalyzer.calculate_complexity(content, language),
            "hash": hashlib.md5(content.encode('utf-8')).hexdigest()
        }
        
        # Add syntax validation
        is_valid, error = CodeAnalyzer.validate_syntax(content, language)
        summary["syntax_valid"] = is_valid
        if error:
            summary["syntax_error"] = error
        
        return summary
