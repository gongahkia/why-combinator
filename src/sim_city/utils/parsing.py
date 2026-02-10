import json
import re
from typing import Dict, Any, Optional

def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract JSON object from text.
    Handles code blocks ```json ... ``` or just raw JSON.
    """
    try:
        # Try direct parse
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Look for code blocks
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Look for first { and last }
    match = re.search(r'(\{.*\})', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
            
    return None
