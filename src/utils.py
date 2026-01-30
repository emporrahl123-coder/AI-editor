"""
Utility functions for GitHub AI Editor
"""

import os
import json
import logging
import hashlib
import re
import random
import string
from typing import Dict, List, Any, Optional
from pathlib import Path
import datetime
import time

def setup_logging(log_level: str = "INFO", log_file: str = "logs/app.log") -> logging.Logger:
    """
    Set up logging configuration
    
    Args:
        log_level: Logging level
        log_file: Log file path
        
    Returns:
        Logger instance
    """
    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger("github_ai_editor")
    return logger

def validate_github_url(url: str) -> bool:
    """
    Validate GitHub repository URL
    
    Args:
        url: URL to validate
        
    Returns:
        True if valid GitHub URL
    """
    patterns = [
        r'^https://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(?:\.git)?$',
        r'^git@github\.com:[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(?:\.git)?$'
    ]
    
    for pattern in patterns:
        if re.match(pattern, url):
            return True
    
    return False

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe filesystem operations
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove path traversal attempts
    filename = os.path.basename(filename)
    
    # Replace unsafe characters
    unsafe_chars = r'[<>:"/\\|?*\x00-\x1f]'
    filename = re.sub(unsafe_chars, '_', filename)
    
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255 - len(ext)] + ext
    
    return filename

def generate_request_id() -> str:
    """
    Generate unique request ID
    
    Returns:
        Request ID string
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"req_{timestamp}_{random_str}"

def format_file_size(bytes_size: int) -> str:
    """
    Format file size in human-readable format
    
    Args:
        bytes_size: Size in bytes
        
    Returns:
        Formatted size string
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} TB"

def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Truncate text with ellipsis
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."

def safe_json_dumps(data: Any, indent: int = 2) -> str:
    """
    Safely convert data to JSON string
    
    Args:
        data: Data to convert
        indent: JSON indentation
        
    Returns:
        JSON string
    """
    def default_serializer(obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        elif isinstance(obj, set):
            return list(obj)
        return str(obj)
    
    return json.dumps(data, default=default_serializer, indent=indent, ensure_ascii=False)

def calculate_md5(content: str) -> str:
    """
    Calculate MD5 hash of content
    
    Args:
        content: Content to hash
        
    Returns:
        MD5 hash string
    """
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def ensure_directory(path: str) -> bool:
    """
    Ensure directory exists
    
    Args:
        path: Directory path
        
    Returns:
        True if directory exists or was created
    """
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logging.error(f"Failed to create directory {path}: {e}")
        return False

def retry_operation(operation, max_retries: int = 3, delay: float = 1.0, 
                   exceptions: tuple = (Exception,)):
    """
    Retry an operation with exponential backoff
    
    Args:
        operation: Function to retry
        max_retries: Maximum number of retries
        delay: Initial delay between retries
        exceptions: Exceptions to catch
        
    Returns:
        Operation result
        
    Raises:
        Last exception if all retries fail
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return operation()
        except exceptions as e:
            last_exception = e
            if attempt < max_retries:
                sleep_time = delay * (2 ** attempt)  # Exponential backoff
                time.sleep(sleep_time)
    
    raise last_exception

def parse_github_ssh_url(ssh_url: str) -> Optional[Dict[str, str]]:
    """
    Parse GitHub SSH URL
    
    Args:
        ssh_url: SSH URL (git@github.com:owner/repo.git)
        
    Returns:
        Dictionary with owner and repo, or None
    """
    pattern = r'git@github\.com:([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)(?:\.git)?'
    match = re.match(pattern, ssh_url)
    
    if match:
        return {
            "owner": match.group(1),
            "repo": match.group(2)
        }
    
    return None

def get_file_extension(filename: str) -> str:
    """
    Get file extension in lowercase
    
    Args:
        filename: Filename
        
    Returns:
        File extension (with dot)
    """
    return Path(filename).suffix.lower()

def is_text_file(content: bytes) -> bool:
    """
    Check if content is likely text
    
    Args:
        content: File content as bytes
        
    Returns:
        True if content appears to be text
    """
    try:
        # Try to decode as UTF-8
        content.decode('utf-8')
        return True
    except UnicodeDecodeError:
        return False

def create_temp_file(content: str, suffix: str = ".tmp") -> str:
    """
    Create temporary file with content
    
    Args:
        content: File content
        suffix: File suffix
        
    Returns:
        Path to temporary file
    """
    import tempfile
    
    fd, path = tempfile.mkstemp(suffix=suffix, text=True)
    
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(content)
    except Exception:
        os.unlink(path)
        raise
    
    return path

def cleanup_temp_files(file_paths: List[str]):
    """
    Clean up temporary files
    
    Args:
        file_paths: List of file paths to delete
    """
    for path in file_paths:
        try:
            if os.path.exists(path):
                os.unlink(path)
        except Exception as e:
            logging.warning(f"Failed to delete temp file {path}: {e}")

def rate_limit_delay(last_request_time: float, min_interval: float = 1.0) -> float:
    """
    Calculate delay needed for rate limiting
    
    Args:
        last_request_time: Timestamp of last request
        min_interval: Minimum time between requests
        
    Returns:
        Time to sleep in seconds
    """
    elapsed = time.time() - last_request_time
    if elapsed < min_interval:
        return min_interval - elapsed
    return 0.0

def validate_email(email: str) -> bool:
    """
    Validate email address format
    
    Args:
        email: Email address
        
    Returns:
        True if valid email format
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def extract_code_blocks(text: str, language: str = None) -> List[Dict[str, str]]:
    """
    Extract code blocks from markdown text
    
    Args:
        text: Markdown text
        language: Filter by language
        
    Returns:
        List of code blocks
    """
    code_blocks = []
    
    # Pattern for markdown code blocks
    if language:
        pattern = rf'```{language}\n(.*?)```'
    else:
        pattern = r'```(\w*)\n(.*?)```'
    
    matches = re.finditer(pattern, text, re.DOTALL)
    
    for match in matches:
        if language:
            code = match.group(1)
            lang = language
        else:
            lang = match.group(1)
            code = match.group(2)
        
        code_blocks.append({
            "language": lang or "unknown",
            "code": code.strip()
        })
    
    return code_blocks

def remove_sensitive_info(text: str) -> str:
    """
    Remove potentially sensitive information from text
    
    Args:
        text: Text to sanitize
        
    Returns:
        Sanitized text
    """
    # Remove API keys
    text = re.sub(r'api[_-]?key["\']?\s*[:=]\s*["\'][^"\']+["\']', 'api_key = "***"', text, flags=re.IGNORECASE)
    
    # Remove tokens
    text = re.sub(r'token["\']?\s*[:=]\s*["\'][^"\']+["\']', 'token = "***"', text, flags=re.IGNORECASE)
    
    # Remove passwords
    text = re.sub(r'password["\']?\s*[:=]\s*["\'][^"\']+["\']', 'password = "***"', text, flags=re.IGNORECASE)
    
    # Remove secret keys
    text = re.sub(r'secret[_-]?key["\']?\s*[:=]\s*["\'][^"\']+["\']', 'secret_key = "***"', text, flags=re.IGNORECASE)
    
    return text

def human_readable_time(seconds: float) -> str:
    """
    Convert seconds to human-readable time
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Human-readable time string
    """
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} minutes"
    else:
        hours = seconds / 3600
        return f"{hours:.1f} hours"
