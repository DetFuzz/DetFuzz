from typing import Dict, Any, List
import json
from pathlib import Path
from openai import OpenAI
from mutation import simple_fitness
from mutation import llm_mutation


def _load_database() -> List[Dict[str, Any]]:
    """Load database file"""
    try:
        with open("database.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _extract_cues(fuzz_strategy: Any) -> List[str]:
    """Extract clue parameters from fuzz_strategy"""
    if isinstance(fuzz_strategy, dict):
        return list(fuzz_strategy.keys())
    elif isinstance(fuzz_strategy, list):
        return fuzz_strategy
    return []


def _get_cues_from_database(function_category: str) -> List[str]:
    """Get cues from database based on function_category"""
    database = _load_database()
    for item in database:
        if item.get("function_category") == function_category:
            return _extract_cues(item.get("fuzz_strategy", []))
    return []


def build_prompt(prompt_template: str, cues: list = None, operation_type: str = "", function_category: str = "") -> str:
    prompt_filled = prompt_template.replace("{cues}", str(cues) if cues else "[]")
    prompt_filled = prompt_filled.replace("{operation_type}", operation_type)
    prompt_filled = prompt_filled.replace("{function_category}", function_category)
    return prompt_filled


def build_prerequisites_prompt(prompt_template: str, data_packet: str, target: str, prerequisites: str = "") -> str:
    """Construct prerequisite prompts"""
    prompt_filled = prompt_template.replace("{DATA_PACKET}", data_packet)
    prompt_filled = prompt_filled.replace("{TARGET}", target)
    prompt_filled = prompt_filled.replace("{PREREQUISITES}", prerequisites)
    return prompt_filled


def _extract_data_packet_from_prompt(full_prompt: str) -> str:
    """Extract DATA_PACKET from full_prompt"""
    import re
    # Attempt to extract DATA_PACKET from the prompt
    # The expected format is typically: DATA Packet: ... or - DATA Packet: ...
    match = re.search(r'\*\*DATA Packet\*\*[:\s]*`([^`]+)`', full_prompt, re.IGNORECASE)
    if match:
        return match.group(1)
    # If not found, attempt to search for alternative formats
    match = re.search(r'DATA Packet[:\s]*`([^`]+)`', full_prompt, re.IGNORECASE)
    if match:
        return match.group(1)
    return ""


def get_prerequisites_for_target(
    client: OpenAI,
    model: str,
    data_packet: str,
    target: str,
    prerequisites: str,
    output_mode: str = "2"
) -> Dict[str, Any]:
    """
    Get prerequisites for a single target parameter.

    Args:
        client: OpenAI client instance used for API requests.
        model (str): The name of the model to use.
        data_packet (str): The raw data packet string.
        target (str): The target parameter (e.g., "ssid={overflow}").
        prerequisites (str): The frontend source code or related context.
        output_mode (str): The specified output format or mode.

    Returns:
        dict: A dictionary containing 'Target', 'prerequisites', and 'other_param'.
    """
    # Read the prerequisites.md template
    workspace = Path(__file__).resolve().parent
    prompt_path = workspace / "prompt" / "prerequisites.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prerequisites prompt not found: {prompt_path}")
    
    prompt_template = prompt_path.read_text(encoding="utf-8")
    full_prompt = build_prerequisites_prompt(prompt_template, data_packet, target, prerequisites)
    
    system_message = "You are a senior IoT fuzzing expert. Strictly follow the specifications in prompt/prerequisites.md for output formatting."
    
    if output_mode == "2":
        print(f"\n[Call LLM] Get prerequisites (prerequisites)")
        print(f"Model: {model}")
        print(f"Target Parameters: {target}")
        print(f"System Message:")
        print("-" * 60)
        print(system_message)
        print("-" * 60)
        print(f"User Message (Prompt):")
        print("-" * 60)
        print(full_prompt)
        print("-" * 60)
    
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": full_prompt},
        ],
        temperature=0.1,
    )
    raw_response = resp.choices[0].message.content.strip()
    
    if output_mode == "2":
        print(f"\noutput (Response):")
        print("-" * 60)
        print(raw_response)
        print("-" * 60)
    
    result = parse_result_to_json(raw_response)
    return result


def produce_payloads(model_inputs: Dict[str, Any], fitness_threshold: float = 0.6, max_rounds: int = 3) -> str:

    api_base = model_inputs["OPENAI_API_BASE_GPT3.5"]
    api_key = model_inputs["OPENAI_API_KEY_GPT3.5"]
    model = model_inputs.get("MODEL", "gpt-3.5-turbo")
    operation_type = model_inputs.get("operation_type", "")
    function_category = model_inputs.get("function_category", "")
    uri = model_inputs.get("URI", "")
    output_mode = model_inputs.get("OUTPUT_MODE", "2")
    cues = _get_cues_from_database(function_category)
    
    if output_mode == "2":
        print(f"Selected function_category: {function_category}")
        print(f"Selected cues (from database): {cues}")

    client = OpenAI(api_key=api_key, base_url=api_base)


    used_cues = []          # Used clues (for exclusion), initially empty
    current_cues = cues     # Clues used in the current round

    for round_id in range(max_rounds):
        if output_mode == "2":
            print(f"\n  - 第 {round_id + 1}/{max_rounds} 轮 Payload 生成")
        # At the start of each round, add the currently used clues to the 'used' set
        for cue in current_cues:
            if cue not in used_cues:
                used_cues.append(cue)
        
        full_prompt = build_prompt(model_inputs["full_prompt"], current_cues, operation_type, function_category)
        
        system_message = "You are a senior IoT fuzzing expert. Strictly follow the specifications in prompt/mutation.md for output formatting."
        
        if output_mode == "2":
            print(f"\n[Call LLM] Round {round_id + 1}: Generating payloads")
            print(f"Model: {model}")
            print(f"System Message:")
            print("-" * 60)
            print(system_message)
            print("-" * 60)
            print(f"User Message (Prompt):")
            print("-" * 60)
            print(full_prompt)
            print("-" * 60)
        
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": system_message
                },
                {"role": "user", "content": full_prompt},
            ],
            temperature=0.1,
        )
        raw_response = resp.choices[0].message.content.strip()
        
        if output_mode == "2":
            print(f"\noutput (Response):")
            print("-" * 60)
            print(raw_response)
            print("-" * 60)
        
        response = parse_result_to_json(raw_response)
        items = response.get("items", [])
        if output_mode == "2":
            print(f"  - Parsed {len(items)} candidate target parameters")

        # Print all target parameters first
        print(f"\n生成的 {len(items)} 个目标参数:")
        for idx, item in enumerate(items, start=1):
            target_para = item.get("target", "")
            print(f"  [{idx}] {target_para}")
        
        # Then check for similarity
        # Perform similarity detection for each target parameter; break on the first clue match and proceed to the next parameter
        has_match = False
        for item in items:
            target_para = item.get("target", "")
            if not target_para:
                continue
            
            matched = False
            for clue in current_cues:
                score = simple_fitness(clue, target_para)
                if score >= fitness_threshold:
                    print(f"  - Similarity check passed: Similarity between {clue} and {target_para}: {score:.3f} (Threshold: {fitness_threshold})")
                    matched = True
                    has_match = True
                    break  # Target matched; break the inner loop and continue to the next parameter
            
            if not matched and output_mode == "2":
                print(f"  - Target parameter {target_para} matched no existing clues")
        
        # Similarity check passes if at least one target parameter matches successfully
        if has_match:
            if output_mode == "2":
                print(f"\n>>> Stage: Fetching prerequisites")
            
            # Retrieve DATA_PACKET and PREREQUISITES
            data_packet = model_inputs.get("DATA_PACKET", "")
            if not data_packet:
                # Attempt to extract from full_prompt
                data_packet = _extract_data_packet_from_prompt(full_prompt)
            
            prerequisites = model_inputs.get("PREREQUISITES", "")
            
            # Get prerequisites for each target parameter
            for target_item in items:
                target = target_item.get("target", "")
                if not target:
                    continue
                
                try:
                    prereq_result = get_prerequisites_for_target(
                        client=client,
                        model=model,
                        data_packet=data_packet,
                        target=target,
                        prerequisites=prerequisites,
                        output_mode=output_mode
                    )
                    # Add prerequisite results to the item
                    target_item["prerequisites"] = prereq_result.get("prerequisites", [])
                    target_item["other_param"] = prereq_result.get("other_param", [])
                    
                    print(f"  - Prerequisites for target {target} acquired")
                    print(f"    Prerequisites: {prereq_result.get('prerequisites', [])}")
                    print(f"    Other Parameters: {prereq_result.get('other_param', [])}")
                except Exception as e:
                    if output_mode == "2":
                        print(f"  - Failed to acquire prerequisites for target {target}: {e}")
                    # Continue processing other parameters even if one fails
                    target_item["prerequisites"] = []
                    target_item["other_param"] = []
            
            return response
        
        print(f"  - Similarity check failed; skipping to the next iteration...")

        # If there is a next round, generate new clues
        if round_id < max_rounds - 1:
            # Generate new clues, excluding those already used
            new_cues = llm_mutation(function_category, uri, api_key, api_base, model, used_cues, output_mode)
            
            if new_cues:
                # 
                current_cues = new_cues
                if output_mode == "2":
                    print(f"  - 第{round_id + 1}轮变异生成了 {len(new_cues)} 个新线索: {new_cues}")
            else:
                if output_mode == "2":
                    print(f"  - 第{round_id + 1}轮变异未生成新线索，继续使用当前线索")
                # 

    
    return response


def parse_result_to_json(text: str) -> Any:
    import json
    import re

    def _sanitize_trailing_commas(s: str) -> str:
        # Strip trailing commas from objects and arrays to improve fault tolerance
        s = re.sub(r",(\s*[}\]])", r"\1", s)
        return s

    # 1.strip out all backticks (```)
    cleaned = text.replace("```", "")
    
    # 2.Use regex to match the string 'json' and capture everything following it
    match = re.search(r"json\s*([\s\S]*)", cleaned, re.IGNORECASE)
    if match:
        json_content = match.group(1).strip()
        # Strip potential leading and trailing quotes
        if json_content.startswith("'") or json_content.startswith('"'):
            json_content = json_content[1:]
        if json_content.endswith("'") or json_content.endswith('"'):
            json_content = json_content[:-1]
        json_content = json_content.strip()
        
        # Attempting to parse
        try:
            return json.loads(_sanitize_trailing_commas(json_content))
        except Exception:
            # If it fails, attempt to extract the first '{ ... }' fragmen
            m = re.search(r"\{[\s\S]*\}", json_content)
            if m:
                try:
                    return json.loads(_sanitize_trailing_commas(m.group(0)))
                except Exception:
                    pass
    
    # If 'json' is not found, attempt to parse the text directly after stripping the backticks
    try:
        return json.loads(_sanitize_trailing_commas(cleaned.strip()))
    except Exception:
        # "As a last resort, attempt to extract the first '{ ... }' fragment
        m = re.search(r"\{[\s\S]*\}", cleaned)
        if m:
            try:
                return json.loads(_sanitize_trailing_commas(m.group(0)))
            except Exception:
                pass

    # "If parsing still fails, log debug information and raise an exception
    print("JSON parsing failed. Raw text (truncated):")
    print(f"'{text[:500]}...'" if len(text) > 500 else f"'{text}'")
    raise ValueError(f"Failed to parse JSON response: {text[:100]}...")
