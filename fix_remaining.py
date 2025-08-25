#!/usr/bin/env python3
"""
Fix remaining critical flake8 issues
"""
import re

files_to_fix = {
    'app/analytics/failure_clustering.py': [
        ('from typing import Dict, List, Any, Tuple', 'from typing import Dict, List, Any'),
    ],
    'app/main.py': [
        ('        from app.orchestrator.queue import get_queue_manager', '        # from app.orchestrator.queue import get_queue_manager'),
    ],
    'app/middleware/auth.py': [
        ('from typing import Optional, Dict, Any, List', 'from typing import Optional, Dict, List'),
        ('import secrets', '# import secrets'),
    ],
    'app/orchestrator/resume.py': [
        ('        now = datetime.now()', '        # now = datetime.now()  # TODO: Use for timeout calculation'),
    ],
    'app/orchestrator/scheduler.py': [
        ('import os', '# import os'),
        ('import re', '# import re'),
        ('from typing import Dict, List, Optional, Any, Union', 'from typing import Dict, List, Optional, Any'),
        ('from dataclasses import dataclass, asdict', 'from dataclasses import dataclass'),
        ('import croniter', '# import croniter'),
    ],
    'app/orchestrator/watcher.py': [
        ('import time', '# import time'),
        ('from datetime import datetime, timedelta', 'from datetime import datetime'),
        ('from dataclasses import dataclass, asdict', 'from dataclasses import dataclass'),
        ('from watchdog.events import FileSystemEvent, FileCreatedEvent, FileModifiedEvent', 'from watchdog.events import FileSystemEvent'),
    ],
    'app/orchestrator/webhook.py': [
        ('import os', '# import os'),
        ('from typing import Dict, List, Optional, Any, Union', 'from typing import Dict, List, Optional, Any'),
        ('from fastapi import FastAPI, Request, Header', 'from fastapi import FastAPI, Request'),
    ],
    'app/security/secrets.py': [
        ('import json', '# import json'),
        ('from datetime import datetime, timedelta', 'from datetime import datetime'),
        ('from typing import Dict, Optional, List, Any, Union', 'from typing import Dict, Optional, List, Any'),
        ('from cryptography.hazmat.primitives import hashes', '# from cryptography.hazmat.primitives import hashes'),
        ('from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC', '# from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC'),
        ('        last_error = str(e)', '        # last_error = str(e)  # TODO: Use for error reporting'),
    ]
}

for file_path, fixes in files_to_fix.items():
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        original_content = content
        
        for old, new in fixes:
            content = content.replace(old, new)
        
        if content != original_content:
            with open(file_path, 'w') as f:
                f.write(content)
            print(f"Fixed {file_path}")
                
    except FileNotFoundError:
        print(f"File not found: {file_path}")
    except Exception as e:
        print(f"Error processing {file_path}: {e}")

print("Finished fixing remaining issues")