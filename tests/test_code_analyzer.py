"""
Tests for code analyzer
"""

import pytest
from src.code_analyzer import CodeAnalyzer

class TestCodeAnalyzer:
    
    def test_detect_language_by_extension(self):
        """Test language detection by file extension"""
        assert CodeAnalyzer.detect_language("test.py") == "python"
        assert CodeAnalyzer.detect_language("script.js") == "javascript"
        assert CodeAnalyzer.detect_language("data.json") == "json"
        assert CodeAnalyzer.detect_language("README.md") == "markdown"
        assert CodeAnalyzer.detect_language("Dockerfile") == "dockerfile"
        assert CodeAnalyzer.detect_language(".gitignore") == "gitignore"
    
    def test_detect_language_by_shebang(self):
        """Test language detection by shebang"""
        content = "#!/usr/bin/env python3\nprint('Hello')"
        assert CodeAnalyzer.detect_language("script", content) == "python"
        
        content = "#!/bin/bash\necho 'Hello'"
        assert CodeAnalyzer.detect_language("script", content) == "bash"
    
    def test_analyze_python_code(self):
        """Test Python code analysis"""
        python_code = """
import os
import sys

def hello(name: str) -> str:
    \"\"\"Say hello to someone.\"\"\"
    return f"Hello, {name}!"

class Calculator:
    \"\"\"Simple calculator class.\"\"\"
    
    def add(self, a: int, b: int) -> int:
        return a + b
"""
        
        analysis = CodeAnalyzer.analyze_python_code(python_code)
        
        assert analysis["valid"] is True
        assert len(analysis["imports"]) == 2  # os and sys
        assert len(analysis["functions"]) == 2  # hello and add
        assert len(analysis["classes"]) == 1  # Calculator
        assert any("Say hello" in doc for doc in analysis["docstrings"])
    
    def test_analyze_json_code(self):
        """Test JSON code analysis"""
        valid_json = '{"name": "test", "value": 42}'
        invalid_json = '{name: test}'
        
        valid_analysis = CodeAnalyzer.analyze_json_code(valid_json)
        invalid_analysis = CodeAnalyzer.analyze_json_code(invalid_json)
        
        assert valid_analysis["valid"] is True
        assert invalid_analysis["valid"] is False
        assert "syntax_error" in invalid_analysis
    
    def test_validate_python_syntax(self):
        """Test Python syntax validation"""
        valid_python = "def test():\n    pass\n"
        invalid_python = "def test()\n    pass\n"
        
        valid, error = CodeAnalyzer.validate_python_syntax(valid_python)
        assert valid is True
        assert error is None
        
        valid, error = CodeAnalyzer.validate_python_syntax(invalid_python)
        assert valid is False
        assert error is not None
    
    def test_validate_json_syntax(self):
        """Test JSON syntax validation"""
        valid_json = '{"test": "value"}'
        invalid_json = '{test: value}'
        
        valid, error = CodeAnalyzer.validate_json_syntax(valid_json)
        assert valid is True
        assert error is None
        
        valid, error = CodeAnalyzer.validate_json_syntax(invalid_json)
        assert valid is False
        assert error is not None
    
    def test_get_file_dependencies(self):
        """Test dependency extraction"""
        python_code = """
import os
from sys import argv
import numpy as np
from pandas import DataFrame
"""
        
        deps = CodeAnalyzer.get_file_dependencies(python_code, "python")
        
        assert "os" in deps
        assert "sys" in deps
        assert "numpy" in deps
        assert "pandas" in deps
    
    def test_compare_files(self):
        """Test file comparison"""
        old_content = "line1\nline2\nline3\n"
        new_content = "line1\nline2 modified\nline3\nline4\n"
        
        comparison = CodeAnalyzer.compare_files(old_content, new_content)
        
        assert comparison["changed"] is True
        assert comparison["additions"] > 0
        assert comparison["deletions"] > 0
        assert comparison["similarity"] < 1.0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
