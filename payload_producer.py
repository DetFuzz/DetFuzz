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
    """构建前置条件提示词"""
    prompt_filled = prompt_template.replace("{DATA_PACKET}", data_packet)
    prompt_filled = prompt_filled.replace("{TARGET}", target)
    prompt_filled = prompt_filled.replace("{PREREQUISITES}", prerequisites)
    return prompt_filled


def _extract_data_packet_from_prompt(full_prompt: str) -> str:
    """从 full_prompt 中提取 DATA_PACKET"""
    import re
    # 尝试从 prompt 中提取 DATA_PACKET
    # 格式通常是: **DATA Packet**: `...` 或 - **DATA Packet**: `...`
    match = re.search(r'\*\*DATA Packet\*\*[:\s]*`([^`]+)`', full_prompt, re.IGNORECASE)
    if match:
        return match.group(1)
    # 如果没找到，尝试查找其他格式
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
    为单个目标参数获取前置条件
    
    Args:
        client: OpenAI 客户端
        model: 模型名称
        data_packet: 数据包字符串
        target: 目标参数（如 "ssid={overflow}"）
        prerequisites: 前端代码
        output_mode: 输出模式
    
    Returns:
        包含 Target, prerequisites, other_param 的字典
    """
    # 读取 prerequisites.md 模板
    workspace = Path(__file__).resolve().parent
    prompt_path = workspace / "prompt" / "prerequisites.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prerequisites prompt not found: {prompt_path}")
    
    prompt_template = prompt_path.read_text(encoding="utf-8")
    full_prompt = build_prerequisites_prompt(prompt_template, data_packet, target, prerequisites)
    
    system_message = "You are a senior IoT fuzzing expert. Strictly follow the specifications in prompt/prerequisites.md for output formatting."
    
    if output_mode == "2":
        print(f"\n[大模型调用] 获取前置条件 (prerequisites)")
        print(f"模型: {model}")
        print(f"目标参数: {target}")
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
        print(f"\n输出 (Response):")
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


    used_cues = []          # 已使用过的线索（用于排除），初始为空
    current_cues = cues     # 当前轮使用的线索

    for round_id in range(max_rounds):
        if output_mode == "2":
            print(f"\n  - 第 {round_id + 1}/{max_rounds} 轮 Payload 生成")
        # 每轮开始时，将当前使用的线索加入已使用集合
        for cue in current_cues:
            if cue not in used_cues:
                used_cues.append(cue)
        
        full_prompt = build_prompt(model_inputs["full_prompt"], current_cues, operation_type, function_category)
        
        system_message = "You are a senior IoT fuzzing expert. Strictly follow the specifications in prompt/mutation.md for output formatting."
        
        if output_mode == "2":
            print(f"\n[大模型调用] 第 {round_id + 1} 轮 Payload 生成")
            print(f"模型: {model}")
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
            print(f"\n输出 (Response):")
            print("-" * 60)
            print(raw_response)
            print("-" * 60)
        
        response = parse_result_to_json(raw_response)
        items = response.get("items", [])
        if output_mode == "2":
            print(f"  - 解析得到 {len(items)} 个候选目标参数")

        # 先打印所有目标参数
        print(f"\n生成的 {len(items)} 个目标参数:")
        for idx, item in enumerate(items, start=1):
            target_para = item.get("target", "")
            print(f"  [{idx}] {target_para}")
        
        # 然后检查相似度
        # 对每个目标参数进行相似度检测，只要匹配到一个线索就 break，继续下一个参数
        has_match = False
        for item in items:
            target_para = item.get("target", "")
            if not target_para:
                continue
            
            matched = False
            for clue in current_cues:
                score = simple_fitness(clue, target_para)
                if score >= fitness_threshold:
                    print(f"  - 相似度检查通过: {clue} 与 {target_para} 的相似度为 {score:.3f} (阈值: {fitness_threshold})")
                    matched = True
                    has_match = True
                    break  # 该目标参数已匹配，break 内层循环，继续下一个目标参数
            
            if not matched and output_mode == "2":
                print(f"  - 目标参数 {target_para} 未匹配到任何线索")
        
        # 如果至少有一个目标参数匹配成功，则通过相似度检查
        if has_match:
            if output_mode == "2":
                print(f"\n>>> 阶段: 获取前置条件 (prerequisites)")
            
            # 获取 DATA_PACKET 和 PREREQUISITES
            data_packet = model_inputs.get("DATA_PACKET", "")
            if not data_packet:
                # 尝试从 full_prompt 中提取
                data_packet = _extract_data_packet_from_prompt(full_prompt)
            
            prerequisites = model_inputs.get("PREREQUISITES", "")
            
            # 为每个目标参数获取前置条件
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
                    # 将前置条件结果添加到 item 中
                    target_item["prerequisites"] = prereq_result.get("prerequisites", [])
                    target_item["other_param"] = prereq_result.get("other_param", [])
                    
                    print(f"  - 目标参数 {target} 的前置条件已获取")
                    print(f"    前置条件: {prereq_result.get('prerequisites', [])}")
                    print(f"    其他参数: {prereq_result.get('other_param', [])}")
                except Exception as e:
                    if output_mode == "2":
                        print(f"  - 获取目标参数 {target} 的前置条件失败: {e}")
                    # 即使失败也继续处理其他参数
                    target_item["prerequisites"] = []
                    target_item["other_param"] = []
            
            return response
        
        print(f"  - 相似度检查未通过，继续下一轮...")

        # 如果还有下一轮，生成新的线索
        if round_id < max_rounds - 1:
            # 生成新线索，排除已使用过的
            new_cues = llm_mutation(function_category, uri, api_key, api_base, model, used_cues, output_mode)
            
            if new_cues:
                # 下一轮只使用新生成的线索
                current_cues = new_cues
                if output_mode == "2":
                    print(f"  - 第{round_id + 1}轮变异生成了 {len(new_cues)} 个新线索: {new_cues}")
            else:
                if output_mode == "2":
                    print(f"  - 第{round_id + 1}轮变异未生成新线索，继续使用当前线索")
                # 如果没有生成新线索，继续使用当前线索

    # 所有轮次结束后返回
    return response


def parse_result_to_json(text: str) -> Any:
    import json
    import re

    def _sanitize_trailing_commas(s: str) -> str:
        # 简单移除对象和数组末尾可能的多余逗号，提升容错
        s = re.sub(r",(\s*[}\]])", r"\1", s)
        return s

    # 1. 首先替换掉所有的 ```
    cleaned = text.replace("```", "")
    
    # 2. 用正则匹配 "json" 这四个字母，读取它后面的全部内容
    match = re.search(r"json\s*([\s\S]*)", cleaned, re.IGNORECASE)
    if match:
        json_content = match.group(1).strip()
        # 去掉开头和结尾可能的引号
        if json_content.startswith("'") or json_content.startswith('"'):
            json_content = json_content[1:]
        if json_content.endswith("'") or json_content.endswith('"'):
            json_content = json_content[:-1]
        json_content = json_content.strip()
        
        # 尝试解析
        try:
            return json.loads(_sanitize_trailing_commas(json_content))
        except Exception:
            # 如果失败，尝试提取第一个 { ... } 片段
            m = re.search(r"\{[\s\S]*\}", json_content)
            if m:
                try:
                    return json.loads(_sanitize_trailing_commas(m.group(0)))
                except Exception:
                    pass
    
    # 如果没有找到 "json"，尝试直接解析去掉 ``` 后的文本
    try:
        return json.loads(_sanitize_trailing_commas(cleaned.strip()))
    except Exception:
        # 最后尝试提取第一个 { ... } 片段
        m = re.search(r"\{[\s\S]*\}", cleaned)
        if m:
            try:
                return json.loads(_sanitize_trailing_commas(m.group(0)))
            except Exception:
                pass

    # 如果仍然解析失败，打印调试信息并抛出异常
    print("JSON解析失败，原始文本（截断）：")
    print(f"'{text[:500]}...'" if len(text) > 500 else f"'{text}'")
    raise ValueError(f"无法解析JSON响应: {text[:100]}...")
