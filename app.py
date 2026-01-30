"""
GitHub AI Editor - Main Flask Application
"""

import os
import json
import logging
import traceback
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from src.config import Config, config
from src.repository_manager import RepositoryManager, RepositoryContext, EditResult
from src.utils import setup_logging, validate_github_url, generate_request_id

# Setup logging
logger = setup_logging(log_level="DEBUG" if config.app.debug else "INFO")

# Initialize Flask app
app = Flask(__name__)
app.secret_key = config.app.secret_key
app.config['MAX_CONTENT_LENGTH'] = config.file.max_file_size_bytes

# Enable CORS
CORS(app)

# Rate limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per hour", "10 per minute"],
    storage_uri="memory://"
)

# Initialize repository manager
repo_manager = RepositoryManager(config)

@app.before_request
def before_request():
    """Log request details"""
    request_id = generate_request_id()
    session['request_id'] = request_id
    
    logger.info(f"Request {request_id}: {request.method} {request.path}")

@app.after_request
def after_request(response):
    """Log response details"""
    request_id = session.get('request_id', 'unknown')
    logger.info(f"Response {request_id}: {response.status_code}")
    return response

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        "error": "Not found",
        "message": "The requested resource was not found"
    }), 404

@app.errorhandler(429)
def ratelimit_handler(error):
    """Handle rate limit errors"""
    return jsonify({
        "error": "Rate limit exceeded",
        "message": "Too many requests. Please try again later."
    }), 429

@app.errorhandler(Exception)
def handle_exception(error):
    """Handle all exceptions"""
    logger.error(f"Unhandled exception: {error}\n{traceback.format_exc()}")
    
    return jsonify({
        "error": "Internal server error",
        "message": str(error),
        "request_id": session.get('request_id', 'unknown')
    }), 500

@app.route('/')
def index():
    """Render main page"""
    return render_template('index.html')

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    })

@app.route('/api/config/summary', methods=['GET'])
def config_summary():
    """Get configuration summary (without sensitive data)"""
    return jsonify(config.get_summary())

@app.route('/api/repository/analyze', methods=['POST'])
@limiter.limit("10 per minute")
def analyze_repository():
    """
    Analyze a GitHub repository
    
    Request JSON:
    {
        "repo_url": "https://github.com/owner/repo"
    }
    """
    data = request.get_json()
    
    if not data or 'repo_url' not in data:
        return jsonify({
            "error": "Missing repo_url in request"
        }), 400
    
    repo_url = data['repo_url']
    
    # Validate URL
    if not validate_github_url(repo_url):
        return jsonify({
            "error": "Invalid GitHub URL",
            "message": "Please provide a valid GitHub repository URL"
        }), 400
    
    try:
        # Analyze repository
        context = repo_manager.analyze_repository(repo_url)
        
        # Return analysis results
        return jsonify({
            "success": True,
            "repository": {
                "owner": context.owner,
                "name": context.repo_name,
                "url": repo_url,
                "description": context.repo_info.description if context.repo_info else None,
                "default_branch": context.default_branch
            },
            "analysis": {
                "file_count": context.file_count,
                "languages": context.languages,
                "important_files": context.important_files[:20],  # Limit response size
                "structure_summary": {
                    "directories": len([k for k, v in context.structure.items() if isinstance(v, dict)]),
                    "files": len([k for k, v in context.structure.items() if isinstance(v, dict) and 'type' in v])
                }
            },
            "request_id": session.get('request_id')
        })
        
    except Exception as e:
        logger.error(f"Failed to analyze repository: {e}")
        return jsonify({
            "error": "Analysis failed",
            "message": str(e),
            "request_id": session.get('request_id')
        }), 500

@app.route('/api/edits/plan', methods=['POST'])
@limiter.limit("5 per minute")
def plan_edits():
    """
    Plan edits for a repository
    
    Request JSON:
    {
        "repo_url": "https://github.com/owner/repo",
        "request": "Add docstrings to all Python functions"
    }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400
    
    repo_url = data.get('repo_url')
    user_request = data.get('request')
    
    if not repo_url or not user_request:
        return jsonify({
            "error": "Missing required fields",
            "required": ["repo_url", "request"]
        }), 400
    
    # Validate URL
    if not validate_github_url(repo_url):
        return jsonify({
            "error": "Invalid GitHub URL"
        }), 400
    
    try:
        # Analyze repository first
        context = repo_manager.analyze_repository(repo_url)
        
        # Plan edits
        plan = repo_manager.plan_edits(context, user_request)
        
        # Convert plan to dictionary
        plan_dict = {
            "instructions": [
                {
                    "file_path": instr.file_path,
                    "change_type": instr.change_type,
                    "description": instr.description,
                    "priority": instr.priority,
                    "context": instr.context
                }
                for instr in plan.instructions
            ],
            "dependencies": plan.dependencies,
            "risks": plan.risks,
            "estimated_time": plan.estimated_time,
            "confidence": plan.confidence
        }
        
        return jsonify({
            "success": True,
            "plan": plan_dict,
            "summary": {
                "instruction_count": len(plan.instructions),
                "estimated_time": plan.estimated_time,
                "confidence": plan.confidence,
                "risks_count": len(plan.risks)
            },
            "request_id": session.get('request_id')
        })
        
    except Exception as e:
        logger.error(f"Failed to plan edits: {e}")
        return jsonify({
            "error": "Planning failed",
            "message": str(e),
            "request_id": session.get('request_id')
        }), 500

@app.route('/api/edits/execute', methods=['POST'])
@limiter.limit("3 per minute")
def execute_edits():
    """
    Execute edits on a repository
    
    Request JSON:
    {
        "repo_url": "https://github.com/owner/repo",
        "request": "Add docstrings to all Python functions",
        "branch_name": "optional-branch-name",
        "create_pr": true
    }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400
    
    repo_url = data.get('repo_url')
    user_request = data.get('request')
    branch_name = data.get('branch_name')
    create_pr = data.get('create_pr', True)
    
    if not repo_url or not user_request:
        return jsonify({
            "error": "Missing required fields",
            "required": ["repo_url", "request"]
        }), 400
    
    # Validate URL
    if not validate_github_url(repo_url):
        return jsonify({
            "error": "Invalid GitHub URL"
        }), 400
    
    try:
        # Generate branch name if not provided
        if not branch_name:
            branch_name = repo_manager.generate_branch_name(user_request)
        
        # Analyze repository
        context = repo_manager.analyze_repository(repo_url)
        
        # Plan edits
        plan = repo_manager.plan_edits(context, user_request)
        
        # Execute edits
        edit_result = repo_manager.execute_edits(context, plan, user_request)
        
        result = {
            "success": edit_result.success,
            "summary": edit_result.summary,
            "changes_count": len(edit_result.changes),
            "errors": edit_result.errors,
            "warnings": edit_result.warnings,
            "branch_name": branch_name,
            "request_id": session.get('request_id')
        }
        
        # Create pull request if requested
        if create_pr and edit_result.success and config.safety.create_branch:
            pr_title, pr_body = repo_manager.generate_pr_details(user_request, edit_result)
            
            pr_result = repo_manager.create_pull_request(
                context=context,
                edit_result=edit_result,
                branch_name=branch_name,
                pr_title=pr_title,
                pr_body=pr_body
            )
            
            if pr_result["success"]:
                result["pull_request"] = {
                    "url": pr_result["pull_request_url"],
                    "number": pr_result.get("pr_number"),
                    "title": pr_result.get("title")
                }
            else:
                result["pull_request_error"] = pr_result.get("error")
        
        # Clean up
        repo_manager.cleanup(context)
        
        # Add change details (limited)
        result["changes_preview"] = [
            {
                "file_path": change.file_path,
                "change_type": change.change_type,
                "language": change.language,
                "validation": change.validation_result
            }
            for change in edit_result.changes[:10]  # Limit to 10 changes
        ]
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Failed to execute edits: {e}")
        return jsonify({
            "error": "Execution failed",
            "message": str(e),
            "traceback": traceback.format_exc() if config.app.debug else None,
            "request_id": session.get('request_id')
        }), 500

@app.route('/api/edits/preview', methods=['POST'])
@limiter.limit("5 per minute")
def preview_edits():
    """
    Preview edits without applying them
    
    Request JSON:
    {
        "repo_url": "https://github.com/owner/repo",
        "request": "Add docstrings to all Python functions"
    }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400
    
    repo_url = data.get('repo_url')
    user_request = data.get('request')
    
    if not repo_url or not user_request:
        return jsonify({
            "error": "Missing required fields"
        }), 400
    
    try:
        # Analyze repository
        context = repo_manager.analyze_repository(repo_url)
        
        # Plan edits
        plan = repo_manager.plan_edits(context, user_request)
        
        # Preview changes (execute but don't write)
        preview_changes = []
        
        for instruction in plan.instructions[:5]:  # Limit to 5 files for preview
            if instruction.change_type != "modify":
                continue
            
            file_path = instruction.file_path
            full_path = Path(context.local_path) / file_path
            
            if not full_path.exists():
                continue
            
            # Read original content
            with open(full_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            # Determine language
            from src.code_analyzer import CodeAnalyzer
            analyzer = CodeAnalyzer()
            language = analyzer.detect_language(file_path, original_content)
            
            # Generate new content
            from src.ai_editor import AIEditor
            ai_editor = AIEditor(
                api_key=config.openai.api_key,
                model=config.openai.model
            )
            
            new_content = ai_editor.edit_file(
                file_content=original_content,
                file_path=file_path,
                language=language,
                instruction=instruction.description,
                context=instruction.context
            )
            
            # Create diff
            import difflib
            diff = list(difflib.unified_diff(
                original_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f'original/{file_path}',
                tofile=f'modified/{file_path}',
                lineterm=''
            ))
            
            preview_changes.append({
                "file_path": file_path,
                "language": language,
                "diff": "\n".join(diff[-50:]),  # Last 50 lines
                "original_preview": original_content[:500],
                "modified_preview": new_content[:500]
            })
        
        # Clean up
        repo_manager.cleanup(context)
        
        return jsonify({
            "success": True,
            "preview_changes": preview_changes,
            "plan_summary": {
                "total_instructions": len(plan.instructions),
                "estimated_time": plan.estimated_time,
                "confidence": plan.confidence
            },
            "request_id": session.get('request_id')
        })
        
    except Exception as e:
        logger.error(f"Failed to preview edits: {e}")
        return jsonify({
            "error": "Preview failed",
            "message": str(e),
            "request_id": session.get('request_id')
        }), 500

@app.route('/api/github/test', methods=['GET'])
def test_github():
    """Test GitHub connection"""
    try:
        # Test with a public repository
        test_url = "https://github.com/octocat/Hello-World"
        context = repo_manager.analyze_repository(test_url)
        
        return jsonify({
            "success": True,
            "message": "GitHub connection successful",
            "test_repository": {
                "owner": context.owner,
                "name": context.repo_name,
                "file_count": context.file_count
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/ai/test', methods=['GET'])
def test_ai():
    """Test AI connection with a simple prompt"""
    try:
        from src.ai_editor import AIEditor
        ai_editor = AIEditor(api_key=config.openai.api_key)
        
        # Simple test
        test_prompt = "Write a Python function that adds two numbers"
        
        response = ai_editor.edit_file(
            file_content="",
            file_path="test.py",
            language="python",
            instruction=test_prompt
        )
        
        return jsonify({
            "success": True,
            "message": "AI connection successful",
            "test_response": response[:200] + "..." if len(response) > 200 else response
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

if __name__ == '__main__':
    # Validate configuration
    config_errors = config.validate()
    
    if config_errors:
        logger.error("Configuration errors:")
        for error in config_errors:
            logger.error(f"  - {error}")
        
        if not config.app.debug:
            logger.error("Cannot start with configuration errors in production")
            exit(1)
    
    # Create necessary directories
    Path("logs").mkdir(exist_ok=True)
    Path("temp").mkdir(exist_ok=True)
    
    # Start Flask app
    logger.info(f"Starting GitHub AI Editor on {config.app.host}:{config.app.port}")
    logger.info(f"Debug mode: {config.app.debug}")
    
    app.run(
        host=config.app.host,
        port=config.app.port,
        debug=config.app.debug
    )
