#!/usr/bin/env python3
"""
Fix common flake8 issues in Phase 4 files
"""
import os
import re
from pathlib import Path

def fix_whitespace_issues(file_path):
    """Fix whitespace and formatting issues"""
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Fix blank lines with whitespace (W293)
    content = re.sub(r'^\s+$', '', content, flags=re.MULTILINE)
    
    # Fix trailing whitespace (W291)
    content = re.sub(r'[ \t]+$', '', content, flags=re.MULTILINE)
    
    # Fix continuation line indentation (E128, E129)
    lines = content.split('\n')
    fixed_lines = []
    in_function_def = False
    
    for i, line in enumerate(lines):
        # Fix common continuation line issues
        if ('=' in line and line.strip().endswith('(') and 
            i + 1 < len(lines) and lines[i + 1].strip().startswith('(')):
            # This is likely a multi-line function call that needs fixing
            fixed_lines.append(line)
            continue
            
        # Fix indentation for continuation lines
        if (line.strip() and not line[0].isalpha() and not line.startswith('    ') and
            not line.startswith('\t') and not line.startswith('#') and
            not line.startswith('@') and len(line) > 0 and line[0] == ' '):
            # Check if this should be indented more
            if i > 0 and ('(' in lines[i-1] or '\\' in lines[i-1]):
                if not line.startswith('        '):  # At least 8 spaces for continuation
                    line = '        ' + line.lstrip()
        
        fixed_lines.append(line)
    
    content = '\n'.join(fixed_lines)
    
    # Fix missing blank lines after class/function definitions (E305, E302)
    content = re.sub(r'(\ndef [^:]+:.*?\n)(^[a-zA-Z@])', r'\1\n\2', content, flags=re.MULTILINE)
    content = re.sub(r'(\nclass [^:]+:.*?\n)(^[a-zA-Z@])', r'\1\n\2', content, flags=re.MULTILINE)
    
    # Fix too many blank lines (E303)
    content = re.sub(r'\n\n\n\n+', '\n\n\n', content)
    
    # Ensure file ends with newline (W292)
    if content and not content.endswith('\n'):
        content += '\n'
    
    # Only write if content changed
    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"Fixed {file_path}")
        return True
    return False

def remove_unused_imports(file_path):
    """Remove some obvious unused imports"""
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Common unused imports in Phase 4 files
    unused_patterns = [
        r'^import os\n',
        r'^import re\n', 
        r'^import time\n',
        r'^import threading\n',
        r'^from datetime import timedelta\n',
        r'^from dataclasses import asdict\n',
        r'^import croniter\n',
        r'^from typing import Union\n',
        r'^from collections import defaultdict\n',
        r'^from typing import Tuple\n',
        r'^import json(?=\n)',  # Only if standalone
        r'^import base64\n',
        r'^from fastapi import Header\n',
        r'^import secrets(?=\n)',  # Only if standalone
        r'^from typing import Any(?=\n)',  # Only if standalone import
    ]
    
    for pattern in unused_patterns:
        if re.search(pattern, content, re.MULTILINE):
            # Check if it's actually used in the file
            import_name = re.search(r'import (\w+)', pattern)
            if import_name:
                name = import_name.group(1)
                if name not in content.replace(pattern.replace('^', '').replace('\\n', ''), ''):
                    content = re.sub(pattern, '', content, flags=re.MULTILINE)
    
    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"Removed unused imports from {file_path}")
        return True
    return False

def main():
    """Fix flake8 issues in Phase 4 files"""
    phase4_files = [
        'app/main.py',
        'app/metrics.py', 
        'app/analytics/failure_clustering.py',
        'app/middleware/auth.py',
        'app/orchestrator/resume.py',
        'app/orchestrator/scheduler.py',
        'app/orchestrator/watcher.py', 
        'app/orchestrator/webhook.py',
        'app/security/secrets.py',
        'app/security/rbac.py',
        'app/dsl/runner.py',
        'app/dsl/validator.py'
    ]
    
    fixed_count = 0
    
    for file_path in phase4_files:
        if os.path.exists(file_path):
            if fix_whitespace_issues(file_path):
                fixed_count += 1
            if remove_unused_imports(file_path):
                fixed_count += 1
    
    print(f"\nFixed {fixed_count} files")

if __name__ == "__main__":
    main()