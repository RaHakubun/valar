"""
工具函数
借鉴前作的类型系统，但不直接修改前作代码
"""

import yaml
import json
import re
from typing import Dict, List, Any, Tuple, Optional


def load_node_definitions(yaml_path: str) -> Dict[str, Any]:
    """
    加载节点定义（从前作的YAML文件）
    
    Args:
        yaml_path: YAML文件路径
        
    Returns:
        节点定义字典
    """
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"警告: 未找到节点定义文件 {yaml_path}")
        return {}
    except Exception as e:
        print(f"加载节点定义失败: {e}")
        return {}


def extract_node_types_from_code(code: str) -> List[str]:
    """
    从代码中提取所有节点类型
    
    Args:
        code: 工作流代码
        
    Returns:
        节点类型列表
    """
    # 正则匹配：var_X = NodeType(...)
    pattern = r'=\s*([A-Z][A-Za-z0-9_]*)\s*\('
    matches = re.findall(pattern, code)
    return list(set(matches))


def extract_node_types_from_json(workflow_json: Dict[str, Any]) -> List[str]:
    """
    从JSON中提取所有节点类型
    
    Args:
        workflow_json: 工作流JSON
        
    Returns:
        节点类型列表
    """
    node_types = []
    for node_id, node_data in workflow_json.items():
        if isinstance(node_data, dict) and 'class_type' in node_data:
            node_types.append(node_data['class_type'])
    return list(set(node_types))


def parse_code_line(line: str) -> Optional[Dict[str, Any]]:
    """
    解析单行代码，提取变量、函数名、参数
    
    Args:
        line: 代码行
        
    Returns:
        解析结果字典或None
    """
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    
    # 匹配: var_1 = FunctionName(param1=value1, param2=value2)
    # 或: var_1, var_2 = FunctionName(...)
    match = re.match(r'([^=]+)\s*=\s*([A-Z][A-Za-z0-9_]*)\s*\((.*)\)', line)
    if not match:
        return None
    
    outputs_str = match.group(1).strip()
    func_name = match.group(2).strip()
    params_str = match.group(3).strip()
    
    # 解析输出变量
    outputs = [v.strip() for v in outputs_str.split(',')]
    
    # 解析参数
    params = {}
    if params_str:
        # 简单分割（不处理嵌套括号等复杂情况）
        for param in params_str.split(','):
            param = param.strip()
            if '=' in param:
                key, value = param.split('=', 1)
                params[key.strip()] = value.strip()
    
    return {
        'outputs': outputs,
        'function': func_name,
        'params': params,
        'raw': line
    }


def infer_output_types(func_name: str, node_defs: Dict[str, Any]) -> Dict[int, str]:
    """
    推断函数的输出类型
    
    Args:
        func_name: 函数名（节点类型）
        node_defs: 节点定义
        
    Returns:
        {索引: 类型} 映射
    """
    if func_name not in node_defs:
        return {}
    
    output_params = node_defs[func_name].get('output_params', {})
    
    output_types = {}
    sorted_outputs = []
    
    for output_key in output_params:
        try:
            key_num = int(output_key.split('_')[-1])
        except (IndexError, ValueError):
            key_num = len(sorted_outputs)
        sorted_outputs.append((key_num, output_key))
    
    sorted_outputs.sort(key=lambda x: x[0])
    
    for index, (_, output_key) in enumerate(sorted_outputs):
        output_type = output_params[output_key]
        output_types[index] = output_type
    
    return output_types


def infer_input_types(func_name: str, node_defs: Dict[str, Any]) -> Dict[str, str]:
    """
    推断函数的输入类型
    
    Args:
        func_name: 函数名（节点类型）
        node_defs: 节点定义
        
    Returns:
        {参数名: 类型} 映射
    """
    if func_name not in node_defs:
        return {}
    
    input_params = node_defs[func_name].get('input_params', {})
    
    input_types = {}
    for param_name, param_info in input_params.items():
        param_type = param_info.get('type', '')
        
        # 处理列表类型（枚举）
        if isinstance(param_type, list):
            # 如果是类型列表，取第一个作为代表
            input_types[param_name] = param_type[0] if param_type else 'ANY'
        else:
            input_types[param_name] = param_type
    
    return input_types


def analyze_code_fragment_io(code: str, node_defs: Dict[str, Any]) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    分析代码片段的输入输出
    
    Args:
        code: 代码片段
        node_defs: 节点定义
        
    Returns:
        (inputs, outputs) 元组
    """
    lines = code.strip().split('\n')
    
    # 记录所有定义的变量
    defined_vars = {}  # {var_name: type}
    
    # 记录未定义但使用的变量（输入）
    required_vars = {}  # {var_name: type}
    
    # 最后一行的输出变量（输出）
    output_vars = {}
    
    for line in lines:
        parsed = parse_code_line(line)
        if not parsed:
            continue
        
        func_name = parsed['function']
        outputs = parsed['outputs']
        params = parsed['params']
        
        # 分析输出
        output_types = infer_output_types(func_name, node_defs)
        for i, var_name in enumerate(outputs):
            var_type = output_types.get(i, 'ANY')
            defined_vars[var_name] = var_type
            output_vars[var_name] = var_type  # 持续更新
        
        # 分析输入
        input_types = infer_input_types(func_name, node_defs)
        for param_name, param_value in params.items():
            # 检查是否引用变量
            if param_value in defined_vars:
                # 已定义的变量，无需外部输入
                continue
            elif re.match(r'^[a-zA-Z_]\w*$', param_value):
                # 看起来像变量名但未定义 -> 需要外部输入
                expected_type = input_types.get(param_name, 'ANY')
                required_vars[param_value] = expected_type
    
    return required_vars, output_vars


def type_compatible(type1: str, type2: str) -> bool:
    """
    检查两个类型是否兼容
    
    Args:
        type1: 类型1
        type2: 类型2
        
    Returns:
        是否兼容
    """
    if type1 == type2:
        return True
    
    # ANY类型兼容所有类型
    if type1 == 'ANY' or type2 == 'ANY':
        return True
    
    # 处理列表类型
    if isinstance(type1, list) and type2 in type1:
        return True
    if isinstance(type2, list) and type1 in type2:
        return True
    
    # 特殊兼容规则（根据ComfyUI的类型系统）
    compatible_pairs = [
        ('IMAGE', 'MASK'),  # 图像和遮罩可以互转
        ('LATENT', 'LATENT_KEYFRAME'),
        ('CONDITIONING', 'CONDITIONING_KEYFRAME'),
    ]
    
    for t1, t2 in compatible_pairs:
        if (type1 == t1 and type2 == t2) or (type1 == t2 and type2 == t1):
            return True
    
    return False


def generate_fragment_id() -> str:
    """生成唯一的片段ID"""
    import uuid
    return f"frag_{uuid.uuid4().hex[:8]}"


def generate_workflow_id() -> str:
    """生成唯一的工作流ID"""
    import uuid
    return f"wf_{uuid.uuid4().hex[:8]}"


def generate_need_id() -> str:
    """生成唯一的需求ID"""
    import uuid
    return f"need_{uuid.uuid4().hex[:8]}"


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """
    加载配置文件
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        配置字典
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"警告: 配置文件 {config_path} 不存在")
        print("请复制 config.yaml.template 为 config.yaml 并填写配置")
        return {}
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        return {}


def save_json(data: Dict[str, Any], file_path: str):
    """保存JSON文件"""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_json(file_path: str) -> Dict[str, Any]:
    """加载JSON文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)
