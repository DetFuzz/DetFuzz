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
    """从 target 中提取参数名，例如从 'ssid={overflow}' 提取 'ssid'"""
    if "=" in target:
        return target.split("=")[0]
    return target


def _parse_key_value(kv_str: str) -> Tuple[str, str]:
    """解析 key=value 字符串，返回 (key, value)"""
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
    生成所有可能的载荷组合
    
    Args:
        target: 目标参数，如 "ssid={overflow}"
        prerequisites: 前置条件列表，如 [["hideSsid=0", "hideSsid=1"]]
        other_param: 其他参数列表，如 [["security=none", "security=wpapsk"], ["wrlPwd=@Ydid8711", "wrlPwd=Tz624930&"]]
        original_data_packet: 原始数据包，如 "security=none&ssid=Tenda_83B550&hideSsid=0&wrlPwd="
    
    Returns:
        所有可能的载荷字符串列表
    """
    # 解析原始数据包，获取所有参数的键值对（作为默认值）
    original_params = {}
    if original_data_packet:
        for param in original_data_packet.split("&"):
            if param and "=" in param:
                key, value = param.split("=", 1)
                original_params[key] = value
    
    # 解析目标参数
    target_key, target_value = _parse_key_value(target)
    
    # 解析前置条件：每个子数组是一个参数的所有可能值
    # 例如 [["hideSsid=0", "hideSsid=1"]] 表示 hideSsid 可以是 0 或 1
    prereq_param_groups = []
    if prerequisites:
        for prereq_group in prerequisites:
            # 跳过空的子列表（这是正常的，不是异常）
            if not prereq_group:
                continue
            # 每个 prereq_group 是一个参数的所有可能值
            # 例如 ["hideSsid=0", "hideSsid=1"]
            param_values = []
            for kv in prereq_group:
                if kv:  # 跳过空字符串
                    key, value = _parse_key_value(kv)
                    param_values.append((key, value))
            # 只有当 param_values 不为空时才添加
            if param_values:
                prereq_param_groups.append(param_values)
    
    # 解析其他参数：每个子数组是一个参数的所有可能值
    other_param_groups = []
    if other_param:
        for other_group in other_param:
            # 跳过空的子列表（这是正常的，不是异常）
            if not other_group:
                continue
            # 每个 other_group 是一个参数的所有可能值
            # 例如 ["security=none", "security=wpapsk", ...]
            param_values = []
            for kv in other_group:
                if kv:  # 跳过空字符串
                    key, value = _parse_key_value(kv)
                    param_values.append((key, value))
            # 只有当 param_values 不为空时才添加
            if param_values:
                other_param_groups.append(param_values)
    
    # 生成所有排列组合
    all_combinations = []
    
    # 生成前置条件的所有组合
    prereq_combinations = []
    if prereq_param_groups:
        # 使用 product 生成所有前置条件的组合
        # 例如：prereq_param_groups = [[("hideSsid", "0"), ("hideSsid", "1")]]
        # 结果：[[("hideSsid", "0")], [("hideSsid", "1")]]
        for combo in product(*prereq_param_groups):
            prereq_combinations.append(list(combo))
    else:
        # 如果前置条件为空，创建一个空组合（表示不使用任何前置条件）
        prereq_combinations = [[]]
    
    # 生成其他参数的所有组合
    other_combinations = []
    if other_param_groups:
        # 使用 product 生成所有其他参数的组合
        # 例如：other_param_groups = [[("security", "none"), ...], [("wrlPwd", "@Ydid8711"), ...]]
        # 结果：所有可能的组合
        for combo in product(*other_param_groups):
            other_combinations.append(list(combo))
    else:
        # 如果其他参数为空，创建一个空组合（表示不使用任何其他参数）
        other_combinations = [[]]
    
    # 组合前置条件和其他参数
    for prereq_combo in prereq_combinations:
        for other_combo in other_combinations:
            # 构建参数字典
            params = original_params.copy()
            
            # 添加目标参数（覆盖原始值）
            params[target_key] = target_value
            
            # 添加前置条件
            for key, value in prereq_combo:
                params[key] = value
            
            # 添加其他参数
            for key, value in other_combo:
                params[key] = value
            
            # 构建载荷字符串（保持原始数据包中参数的顺序）
            payload_parts = []
            if original_data_packet:
                # 按原始顺序添加参数
                seen_keys = set()
                for param in original_data_packet.split("&"):
                    if param and "=" in param:
                        key = param.split("=", 1)[0]
                        if key in params:
                            payload_parts.append(f"{key}={params[key]}")
                            seen_keys.add(key)
                
                # 添加新出现的参数（不在原始数据包中的，这种情况应该很少）
                for key, value in params.items():
                    if key not in seen_keys:
                        payload_parts.append(f"{key}={value}")
            else:
                # 如果没有原始数据包，直接按字典顺序构建
                for key, value in sorted(params.items()):
                    payload_parts.append(f"{key}={value}")
            
            payload_str = "&".join(payload_parts)
            all_combinations.append(payload_str)
    
    return all_combinations


def write_payload_files(vendor: str, product: str, ui_info: str, result_json: Dict[str, any], workspace: Path, uri: str = "", output_mode: str = "2", data_packet: str = "") -> List[Path]:
    """
    写入载荷文件
    
    Args:
        vendor: 厂商名称
        product: 产品名称
        ui_info: UI 信息
        result_json: 结果 JSON，包含 items 列表
        workspace: 工作空间路径
        uri: URI 路径
        output_mode: 输出模式
        data_packet: 原始数据包
    """
    items: List[Dict[str, str]] = result_json.get("items", [])
    if not isinstance(items, list) or len(items) == 0:
        raise ValueError("result_json.items must be a non-empty list")

    vendor_template = workspace / "prompt" / "poc" / f"{vendor}.py"
    if not vendor_template.exists():
        raise FileNotFoundError(f"Vendor template not found: {vendor_template}")

    if output_mode == "2":
        print(f"  - 读取模板文件: {vendor_template}")
        print(f"  - 准备生成载荷文件")
    
    written: List[Path] = []
    file_id = 1  # 全局文件 ID 计数器
    
    for item in items:
        target = item.get("target", "")
        if not target:
            continue
        
        rtype = str(item.get("type", "cmdi")).lower()
        if rtype not in ("cmdi", "overflow"):
            rtype = "cmdi"
        
        prerequisites = item.get("prerequisites", [])
        other_param = item.get("other_param", [])
        
        # 提取参数名用于文件命名
        param_name = _extract_param_name_from_target(target)
        
        # 生成所有载荷组合
        # 注意：即使 prerequisites 或 other_param 为空，也会至少生成一个载荷（只包含目标参数）
        all_payloads = _generate_all_combinations(
            target=target,
            prerequisites=prerequisites if prerequisites else [],
            other_param=other_param if other_param else [],
            original_data_packet=data_packet
        )
        
        # 确保至少生成一个载荷（即使所有条件都为空）
        if not all_payloads:
            # 如果没有任何载荷，至少生成一个只包含目标参数的载荷
            target_key, target_value = _parse_key_value(target)
            if data_packet:
                # 从原始数据包构建载荷
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
            print(f"  - 目标参数 {target} 生成 {len(all_payloads)} 个载荷组合")
            if not prerequisites and not other_param:
                print(f"    (无前置条件和其他参数，仅使用目标参数)")
        
        # 确定输出目录
        basename = uri if uri else ui_info
        output_dir = workspace / vendor / product / "output" / rtype / basename
        ensure_dir(output_dir)
        
        # 为每个载荷组合写入文件
        for payload in all_payloads:
            filename = f"{basename}_{param_name}_{file_id}.py"
            target_path = output_dir / filename
            
            # 使用空字符串作为 reason（因为现在没有 reason 字段）
            rendered = render_with_template(vendor_template, payload, "", uri)
            target_path.write_text(rendered, encoding="utf-8")
            written.append(target_path)
            
            if output_mode == "2":
                print(f"    ✓ 已写入: {target_path.relative_to(workspace)}")
            
            file_id += 1
    
    if output_mode == "2":
        print(f"  - 总共写入 {len(written)} 个载荷文件")
    
    return written
