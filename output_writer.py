import json
from pathlib import Path
from typing import Dict, List, Tuple
from itertools import product


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def render_with_template(template_path: Path, payload: str, reason: str, uri: str) -> str:
    template = template_path.read_text(encoding="utf-8")
    header = "# " + reason.replace("\n", "\n# ") + "\n" if reason else ""
    rendered = template.replace("payload", payload)
    if uri:
        rendered = rendered.replace("{URI}", f"/{uri}")
    else:
        rendered = rendered.replace("{URI}", "/")
    return header + rendered


def _extract_param_name_from_target(target: str) -> str:
    """Extract parameter names from the target; for example, extract 'ssid' from 'ssid={overflow}'"""
    if "=" in target:
        return target.split("=")[0]
    return target


def _parse_key_value(kv_str: str) -> Tuple[str, str]:
    """Parse the key=value string and return (key, value)"""
    if "=" in kv_str:
        key, value = kv_str.split("=", 1)
        return key, value
    return kv_str, ""


def _generate_all_combinations(
    target: str,
    prerequisites: List[List[str]],
    other_param: List[List[str]],
    original_data_packet: str
) -> List[str]:
    """
    
    Generate all possible payload combinations

    Args: 
        target: The target parameter, e.g., "ssid={overflow}" 
        prerequisites: A list of prerequisites, e.g., [["hideSsid=0", "hideSsid=1"]] 
        other_param: A list of other parameters, e.g., [["security=none", "security=wpapsk"], ["wrlPwd=@Ydid8711", "wrlPwd=Tz624930&"]] 
        original_data_packet: The original data packet, e.g., "security=none&ssid=Tenda_83B550&hideSsid=0&wrlPwd="

    Returns: 
        A list of all possible payload strings
    
    """
    # Parse the original data packet to retrieve key-value pairs for all parameters (to be used as default values)
    original_params = {}
    if original_data_packet:
        for param in original_data_packet.split("&"):
            if param and "=" in param:
                key, value = param.split("=", 1)
                original_params[key] = value
    
    # Parse the target parameter
    target_key, target_value = _parse_key_value(target)
    
    # Parse prerequisites: Each subarray represents all possible values for a single parameter
    # For example, [["hideSsid=0", "hideSsid=1"]] indicates that hideSsid can be either 0 or 1
    prereq_param_groups = []
    if prerequisites:
        for prereq_group in prerequisites:
            # Skip empty sub-lists (this is expected behavior, not an error)
            if not prereq_group:
                continue
            # Each prereq_group represents all possible values for a single parameter
            # e.g., ["hideSsid=0", "hideSsid=1"]
            param_values = []
            for kv in prereq_group:
                if kv:  # Skip empty strings
                    key, value = _parse_key_value(kv)
                    param_values.append((key, value))
            # Only add if param_values is not empty
            if param_values:
                prereq_param_groups.append(param_values)
    
    # Parse other parameters: Each subarray represents all possible values for a single parameter
    other_param_groups = []
    if other_param:
        for other_group in other_param:
            # Skip empty sub-lists (this is expected behavior, not an error)
            if not other_group:
                continue
            # Each other_group represents all possible values for a single parameter
            # e.g., ["security=none", "security=wpapsk", ...]
            param_values = []
            for kv in other_group:
                if kv:  # Skip empty strings
                    key, value = _parse_key_value(kv)
                    param_values.append((key, value))
            # Only add if param_values is not empty
            if param_values:
                other_param_groups.append(param_values)
    
    # Generate all permutations and combinations
    all_combinations = []
    
    # Generate all combinations of preconditions
    prereq_combinations = []
    if prereq_param_groups:
        # Generate all combinations of preconditions using product
        # e.g., prereq_param_groups = [[("hideSsid", "0"), ("hideSsid", "1")]]
        # Result: [[("hideSsid", "0")], [("hideSsid", "1")]]
        for combo in product(*prereq_param_groups):
            prereq_combinations.append(list(combo))
    else:
        # If prerequisites are empty, create an empty combination (indicating no prerequisites are used)
        prereq_combinations = [[]]
    
    # Generate all combinations of other parameters
    other_combinations = []
    if other_param_groups:
        # Use product to generate all combinations of other parameters
        # e.g., other_param_groups = [[("security", "none"), ...], [("wrlPwd", "@Ydid8711"), ...]]
        # Result: All possible combinations
        for combo in product(*other_param_groups):
            other_combinations.append(list(combo))
    else:
        # If other parameters are empty, create an empty combination (indicating no other parameters are used)
        other_combinations = [[]]
    
    # Combine prerequisites and other parameters
    for prereq_combo in prereq_combinations:
        for other_combo in other_combinations:
            # Build the parameter dictionary
            params = original_params.copy()
            
            # Add the target parameter (overwrites the original value)
            params[target_key] = target_value
            
            # Add prerequisites
            for key, value in prereq_combo:
                params[key] = value
            
            # Add other parameters
            for key, value in other_combo:
                params[key] = value
            
            # "Construct the payload string (preserving the order of parameters from the original packet)
            payload_parts = []
            if original_data_packet:
                # Add parameters in their original order
                seen_keys = set()
                for param in original_data_packet.split("&"):
                    if param and "=" in param:
                        key = param.split("=", 1)[0]
                        if key in params:
                            payload_parts.append(f"{key}={params[key]}")
                            seen_keys.add(key)
                
                # Add newly introduced parameters (those not present in the original packet; this should be rare)
                for key, value in params.items():
                    if key not in seen_keys:
                        payload_parts.append(f"{key}={value}")
            else:
                # If no original packet is provided, construct the string in alphabetical order
                for key, value in sorted(params.items()):
                    payload_parts.append(f"{key}={value}")
            
            payload_str = "&".join(payload_parts)
            all_combinations.append(payload_str)
    
    return all_combinations


def write_payload_files(vendor: str, product: str, ui_info: str, result_json: Dict[str, any], workspace: Path, uri: str = "", output_mode: str = "2", data_packet: str = "") -> List[Path]:
    """
    Write payloads to file
    
    Args:
        vendor: Vendor name
        product: Product name
        ui_info: UI information
        result_json: Result JSON containing an items list
        workspace: Path to the workspace directory
        uri: URI path
        output_mode: Mode for outputting results
        data_packet: The original raw data packet
    """
    items: List[Dict[str, str]] = result_json.get("items", [])
    if not isinstance(items, list) or len(items) == 0:
        raise ValueError("result_json.items must be a non-empty list")

    vendor_template = workspace / "prompt" / "poc" / f"{vendor}.py"
    if not vendor_template.exists():
        raise FileNotFoundError(f"Vendor template not found: {vendor_template}")

    if output_mode == "2":
        print(f"  - Read the template file: {vendor_template}")
        print(f"  - Prepare to generate the payload file")
    
    written: List[Path] = []
    file_id = 1  # Global file ID counter
    
    for item in items:
        target = item.get("target", "")
        if not target:
            continue
        
        rtype = str(item.get("type", "cmdi")).lower()
        if rtype not in ("cmdi", "overflow"):
            rtype = "cmdi"
        
        prerequisites = item.get("prerequisites", [])
        other_param = item.get("other_param", [])
        
        # Extract parameter names for file naming
        param_name = _extract_param_name_from_target(target)
        
        # Generate all payload combinations
        # Note: Even if prerequisites or other_params are empty, at least one payload (containing only the target parameter) will be generated
        all_payloads = _generate_all_combinations(
            target=target,
            prerequisites=prerequisites if prerequisites else [],
            other_param=other_param if other_param else [],
            original_data_packet=data_packet
        )
        
        # Ensure at least one payload is generated (even if all conditions are empty)
        if not all_payloads:
            # If no payloads are generated, create at least one payload containing only the target parameter
            target_key, target_value = _parse_key_value(target)
            if data_packet:
                # Construct payload from the original data packet
                params = {}
                for param in data_packet.split("&"):
                    if param and "=" in param:
                        key, value = param.split("=", 1)
                        params[key] = value
                params[target_key] = target_value
                payload_parts = [f"{k}={v}" for k, v in params.items()]
                all_payloads = ["&".join(payload_parts)]
            else:
                all_payloads = [f"{target_key}={target_value}"]
        
        if output_mode == "2":
            print(f"  - Generated {len(all_payloads)} payload combinations for target parameter: {target}")
            if not prerequisites and not other_param:
                print(f"    (No prerequisites or other parameters; using target parameter only)")
        
        # Determine the output directory
        basename = uri if uri else ui_info
        output_dir = workspace / vendor / product / "output" / rtype / basename
        ensure_dir(output_dir)
        
        # Write a file for each payload combination
        for payload in all_payloads:
            filename = f"{basename}_{param_name}_{file_id}.py"
            target_path = output_dir / filename
            
            # Use an empty string for reason (as the field is currently unavailable)
            rendered = render_with_template(vendor_template, payload, "", uri)
            target_path.write_text(rendered, encoding="utf-8")
            written.append(target_path)
            
            if output_mode == "2":
                print(f"    ✓ Successfully written: {target_path.relative_to(workspace)}")
            
            file_id += 1
    
    if output_mode == "2":
        print(f"  - Total of {len(written)} payload files written")
    
    return written
