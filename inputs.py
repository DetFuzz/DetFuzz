import os
from pathlib import Path
from typing import Dict, List, Tuple
from dotenv import load_dotenv


def load_env() -> Dict[str, str]:
    load_dotenv(override=True)
    env = {
        "OPENAI_API_BASE_GPT3.5": os.getenv("OPENAI_API_BASE_GPT3.5", ""),
        "OPENAI_API_KEY_GPT3.5": os.getenv("OPENAI_API_KEY_GPT3.5", ""),
        "MODEL": os.getenv("MODEL", "gpt-3.5-turbo"),
    }
    if not env["OPENAI_API_BASE_GPT3.5"] or not env["OPENAI_API_KEY_GPT3.5"]:
        raise RuntimeError("Missing OPENAI_API_BASE_GPT3.5 or OPENAI_API_KEY_GPT3.5 in environment")
    return env


def read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return path.read_text(encoding="utf-8")


def build_prompt(prompt_template: str, data_packet: str, prerequisites: str = "") -> str:
    prompt_filled = prompt_template.replace("{DATA_PACKET}", data_packet)
    prompt_filled = prompt_filled.replace("{PREREQUISITES}", prerequisites)
    return prompt_filled


def list_ui_inputs(root: Path) -> List[Tuple[str, str, str, str]]:
    items: List[Tuple[str, str, str, str]] = []
    for p in sorted(root.glob("*")):
        if p.is_file():
            stem = p.stem
            if "&" in stem:
                uri, ui_info = stem.split("&", 1)
            else:
                uri, ui_info = "", stem
            content = read_text(p)
            # Use --- to separate data_packet and prerequisites
            if "---" in content:
                parts = content.split("---", 1)
                data_packet = parts[0].strip()
                prerequisites = parts[1].strip() if len(parts) > 1 else ""
            else:
                data_packet = content.strip()
                prerequisites = ""
            items.append((uri, ui_info, data_packet, prerequisites))
    return items


def prepare_inputs(workspace: Path, vendor: str, product: str, output_mode: str = "2") -> List[Dict[str, str]]:
    if output_mode == "2":
        print("  - Load environment variables")
    env = load_env()
    
    if output_mode == "2":
        print("  - Read prompt template: prompt/target_choosing.md")
    prompt_path = workspace / "prompt" / "target_choosing.md"
    prompt_template = read_text(prompt_path)

    input_dir = workspace / vendor / product / "input"
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    if output_mode == "2":
        print(f"  - Scan input directory: {input_dir}")
    jobs: List[Dict[str, str]] = []
    for uri, ui_info, data_packet, prerequisites in list_ui_inputs(input_dir):
        full_prompt = build_prompt(prompt_template, data_packet)
        jobs.append({
            "VENDOR": vendor,
            "PRODUCT": product,
            "URI": uri,
            "UI_INFO": ui_info,
            "DATA_PACKET": data_packet,  # Data packet content
            "PREREQUISITES": prerequisites,  # Frontend HTML code/elements
            "full_prompt": full_prompt,
            **env,
        })
        if output_mode == "2":
            print(f"    ✓ Loaded: {ui_info} (URI: {uri or 'N/A'})")
    return jobs


