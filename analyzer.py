import os
import json
import requests
from typing import Dict, Any, List


def _is_verbose(output_mode: str = "2") -> bool:
    """Check whether to use verbose output (mode 2)."""
    return output_mode == "2"


def _load_database() -> List[Dict[str, Any]]:
    """Load database file"""
    try:
        with open("database.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


# Functionality category configuration
FUNCTION_CATEGORIES = {
    "WiFiSettings": "wifi.",  # *
    "ParentControl": "parental_control.",
    "VPN": "vpn.",
    "USB": "usb.",
    "Bandwidth": "bandwidth.",
    "Power": "power.",  # *
    "Led": "led.",
    "Filter": "filter.",  # *
    "Firewall": "firewall.",
    "IPTV": "iptv.",
    "Route": "route.",  # *
    "DNS": "dns.",
    "DMZ": "dmz.",
    "UPnP": "upnp.",
    "WAN": "wan.",
    "DHCP": "dhcp.",
    "LAN": "lan.",
    "Time": "time.",  # *
    "Login": "login.",  # *
    "RemoteControl": "remote_control.",
    "Diagnostic": "diagnostic.",
    "Log": "log.",
}

def _get_candidate_functions(coarse_category: str) -> List[Dict[str, Any]]:
    """Retrieve candidate functions based on coarse category"""
    database = _load_database()
    
    prefix = FUNCTION_CATEGORIES.get(coarse_category)
    if not prefix:
        return []
    
    return [item for item in database if item.get("function_category", "").startswith(prefix)]


def _function_exists_in_database(function_category: str) -> bool:
    """Check if a function_category exists in the database"""
    database = _load_database()
    return any(item.get("function_category") == function_category for item in database)


def _add_function_to_database(function_category: str, coarse_category: str) -> None:
    """Add a new function to the database, inserting it in the correct position based on coarse_category.
    The fuzz_strategy is automatically set to an empty list [].
    """
    database = _load_database()
    
    # Check if it already exists
    if _function_exists_in_database(function_category):
        return
    
    # Create a new entry programmatically: function_category comes from the LLM, fuzz_strategy is automatically set to an empty list
    new_entry = {
        "function_category": function_category,
        "fuzz_strategy": []
    }
    
    # Retrieve the prefix corresponding to the coarse_category
    prefix = FUNCTION_CATEGORIES.get(coarse_category, "")
    if not prefix:
        # If no prefix is found, append it directly to the end
        database.append(new_entry)
    else:
        # Find the last entry with the same prefix and insert after it
        insert_index = len(database)
        for i, item in enumerate(database):
            func_cat = item.get("function_category", "")
            if func_cat.startswith(prefix):
                # Find entries with the same prefix and update the insertion position
                insert_index = i + 1
        
        # Insert at the determined position
        database.insert(insert_index, new_entry)
    
    # Save to file
    try:
        with open("database.json", "w", encoding="utf-8") as f:
            json.dump(database, f, ensure_ascii=False, indent=4)
        print(f"  - The new functionality has been successfully added to the database: {function_category}")
    except Exception as e:
        print(f"  - Warning: Unable to save to the database: {e}")


def _extract_cues(fuzz_strategy: Any) -> List[str]:
    """Extract clue parameters from fuzz_strategy"""
    if isinstance(fuzz_strategy, dict):
        return list(fuzz_strategy.keys())
    elif isinstance(fuzz_strategy, list):
        return fuzz_strategy
    return []


def _call_openai(prompt: str, max_tokens: int = 1024, step_name: str = "", output_mode: str = "2") -> str:
    """Call the OpenAI API"""
    openai_base = os.getenv("OPENAI_API_BASE_GPT3.5")
    openai_key = os.getenv("OPENAI_API_KEY_GPT3.5")
    model = os.getenv("MODEL", "gpt-3.5-turbo")
    
    if not (openai_base and openai_key):
        return ""
    
    if _is_verbose(output_mode):
        print(f"\n[Large model invocation] {step_name or 'Analyzer'}")
        print(f"model: {model}")
        print(f"input (Prompt):")
        print("-" * 60)
        preview = prompt[:1000]
        print(preview + ("..." if len(prompt) > 1000 else ""))
        if len(prompt) > 1000:
            print(f"... (Total length: {len(prompt)} Characters)")
        print("-" * 60)
    
    try:
        resp = requests.post(
            openai_base.rstrip("/") + "/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {openai_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0,
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        
        if isinstance(data.get("choices"), list) and data["choices"]:
            output = data["choices"][0].get("message", {}).get("content", "")
            if _is_verbose(output_mode):
                print(f"\noutput (Response):")
                print("-" * 60)
                print(output[:1000] + ("..." if len(output) > 1000 else ""))
                if len(output) > 1000:
                    print(f"... (Total length: {len(output)} Characters)")
                print("-" * 60)
            return output
        return ""
    except Exception as e:
        if _is_verbose(output_mode):
            print(f"\n[Error] API call failed: {e}")
        return ""


def _parse_json_response(content: str) -> Dict[str, Any]:
    """Parse JSON response with fault tolerance"""
    try:
        return json.loads(content)
    except Exception:
        import re
        match = re.search(r"\{[\s\S]*\}", content)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
    return {}


def analyze_with_prompt(ui_info: str, uri: str, frontend_code: str = "", output_mode: str = "2") -> Dict[str, Any]:
    # Step 1: Determine the coarse category
    if _is_verbose(output_mode):
        print("  - Step 1: Determine the functional category (coarse_category)")
    category_list = list(FUNCTION_CATEGORIES.keys())
    step1_prompt = f"""
    I will provide information from a network device's management interface. Your task is to classify this information into the most appropriate category.
    
    ### Input Data:
    - UI Text/ID: {ui_info}
    - Endpoint/URL Path: {uri}
    
    ### Classification Rules:
    1. Select the most relevant category from this list: {category_list}
    2. Base your decision on the functionality implied by the UI information and URL.
    3. If multiple categories seem relevant, choose the most specific one.
    
    ### Output Requirement:
    
    Return ONLY a JSON object: {{"coarse_category": "category_name"}}
    """
    
    step1_content = _call_openai(step1_prompt, step_name="Step 1: Determine the category", output_mode=output_mode)
    if not step1_content:
        return {}
    
    step1_result = _parse_json_response(step1_content)
    coarse_category = step1_result.get("coarse_category")
    if not coarse_category:
        return {}
    
    if _is_verbose(output_mode):
        print(f"  - Functional category: {coarse_category}")
        print("  - Step 2: Identify the atomic operation logic (AOL) and operation type")
    candidates = _get_candidate_functions(coarse_category)
    
    # Step 2: Determine the specific function category and operation type
    prefix = FUNCTION_CATEGORIES.get(coarse_category, "")
    
    # Build a candidate functionality list (for display only; does not include cues)
    candidate_list = [item.get("function_category", "") for item in candidates]
    
    step2_prompt = f"""
        You are analyzing IoT device functionality to determine the specific function category and operation type.

        **INPUT INFORMATION:**
        1. UI Information: {ui_info}
        2. URI Path: {uri}
        3. Frontend code: {frontend_code}
        4. Candidate Functions (from database): {json.dumps(candidate_list, ensure_ascii=False, indent=2)}
        5. Coarse Category: {coarse_category} (prefix: {prefix})

        **TASK:**
        Using the input information above, you need to:
        1. Select the most appropriate `function_category` from the candidate functions list. Only when **no candidate is semantically relevant at all** may you create a new one, following the format `{prefix}<function_name>` with `<action>_<target>` naming.
        2. Determine the `operation_type` based on how the function operates.

        **OPERATION TYPE DEFINITIONS:**
        - **set**: Parameters that configure system settings when the function is executed. These parameters generally do not get passed to command execution functions. (e.g., password changes)
        - **get**: Function retrieves system information without modifying state (e.g., device status, configuration reading)
        - **exec**: Parameters are likely to be passed to functions such as doSystemCmd or system. These typically include items like ping destinations, command arguments.
        
        Note: There can be overlaps between exec and set. For example, some key parameters (such as name-type fields) may appear in both configuration and command execution contexts. In such cases, you can return "set&exec".

        **OUTPUT REQUIREMENTS AND FORMAT:**
        {{
            "function_category": "MUST be selected from candidates if any match exists. Only generate new if NO candidate matches.",
            "operation_type": "set|get|exec|set&exec",
        }}
        """
    
    step2_content = _call_openai(step2_prompt, step_name="Step 2: Identify the specific functionality category and operation type", output_mode=output_mode)
    step2_result = {}
    if step2_content:
        step2_result = _parse_json_response(step2_content)

    # Check whether the function_category exists in the database, and add it if it does not
    if step2_result:
        function_category = step2_result.get("function_category", "")
        
        if function_category:
            # Check whether it exists in the database
            if not _function_exists_in_database(function_category):
                # If it does not exist in the database, add it (programmatically setting fuzz_strategy to an empty list)
                if _is_verbose(output_mode):
                    print(f"  - New functionality detected, preparing to add it to the database: {function_category}")
                _add_function_to_database(function_category, coarse_category)
            else:
                if _is_verbose(output_mode):
                    print(f"  - Functionality already exists in the database: {function_category}")

    # Pattern 1: Output only “URL Path：xxx，{"coarse_category": "...", "function_category": "..."}”
    function_category = step2_result.get("function_category", "") if step2_result else ""
    print(f"URL Path：{uri or ''}，{{\"coarse_category\": \"{coarse_category}\", \"function_category\": \"{function_category}\"}}")
    
    if not step2_result:
        return {"coarse_category": coarse_category}

    return step2_result


def analyzer(job: Dict[str, Any]) -> Dict[str, Any]:
    ui_info = job.get("UI_INFO", "")
    uri = job.get("URI", "")
    frontend_code = job.get("PREREQUISITES", "")
    output_mode = job.get("OUTPUT_MODE", "2")
    analysis_result = analyze_with_prompt(ui_info, uri, frontend_code, output_mode)
    job.update(analysis_result)
    return job