"""
工作流拼接模块
借鉴前作的类型匹配思想，实现片段级别的拼接
使用代码表示进行拼接，最后转换为JSON
"""

from typing import List, Dict, Any, Tuple, Optional
from .data_structures import WorkflowFragment, AtomicNeed, WorkflowFramework
from .utils import generate_workflow_id, parse_code_line, type_compatible
import re
import json


class WorkflowAssembler:
    """工作流拼接器"""
    
    def __init__(self, node_defs: Dict[str, Any]):
        """
        初始化拼接器
        
        Args:
            node_defs: 节点定义（从前作的YAML加载）
        """
        self.node_defs = node_defs
    
    def assemble(
        self,
        fragments: List[WorkflowFragment],
        atomic_needs: List[AtomicNeed],
        execution_order: List[str]
    ) -> WorkflowFramework:
        """
        拼接片段为完整工作流框架
        
        Args:
            fragments: 片段列表
            atomic_needs: 原子需求列表
            execution_order: 执行顺序（need_id列表）
            
        Returns:
            工作流框架
        """
        # 按执行顺序组织片段
        ordered_fragments = self._order_fragments_by_needs(
            fragments,
            execution_order
        )
        
        # 拼接代码
        combined_code = self._combine_code_fragments(ordered_fragments)
        
        # 创建工作流框架
        framework = WorkflowFramework(
            framework_id=generate_workflow_id(),
            fragments=ordered_fragments,
            execution_order=[f.fragment_id for f in ordered_fragments],
            framework_code=combined_code
        )
        
        return framework
    
    def _order_fragments_by_needs(
        self,
        fragments: List[WorkflowFragment],
        execution_order: List[str]
    ) -> List[WorkflowFragment]:
        """
        按需求执行顺序组织片段
        
        Args:
            fragments: 片段列表
            execution_order: 需求执行顺序
            
        Returns:
            有序片段列表
        """
        ordered = []
        
        for need_id in execution_order:
            # 找到匹配该需求的片段
            matching_fragments = [
                f for f in fragments 
                if f.mapped_need_id == need_id
            ]
            
            if matching_fragments:
                # 选择置信度最高的
                best_fragment = max(
                    matching_fragments,
                    key=lambda f: f.match_confidence
                )
                ordered.append(best_fragment)
        
        return ordered
    
    def _combine_code_fragments(
        self,
        fragments: List[WorkflowFragment]
    ) -> str:
        """
        拼接代码片段
        
        核心逻辑：
        1. 重命名变量以避免冲突
        2. 自动连接输入输出
        3. 保持依赖关系正确
        
        Args:
            fragments: 有序片段列表
            
        Returns:
            组合后的代码
        """
        if not fragments:
            return ""
        
        # 变量重命名映射
        var_counter = 1
        var_mapping = {}  # {old_var: new_var}
        type_mapping = {}  # {var_name: type}
        
        combined_lines = []
        
        for i, fragment in enumerate(fragments):
            fragment_lines = fragment.code.strip().split('\n')
            
            for line in fragment_lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # 解析这一行
                parsed = parse_code_line(line)
                if not parsed:
                    combined_lines.append(line)
                    continue
                
                func_name = parsed['function']
                outputs = parsed['outputs']
                params = parsed['params']
                
                # 处理输出变量（重命名）
                new_outputs = []
                for old_var in outputs:
                    if old_var not in var_mapping:
                        new_var = f'var_{var_counter}'
                        var_mapping[old_var] = new_var
                        var_counter += 1
                    else:
                        new_var = var_mapping[old_var]
                    
                    new_outputs.append(new_var)
                
                # 处理输入参数（连接到前面的输出）
                new_params = {}
                for param_name, param_value in params.items():
                    # 去除引号
                    param_value_clean = param_value.strip('\'"')
                    
                    # 检查是否是变量引用
                    if param_value_clean in var_mapping:
                        # 引用之前定义的变量
                        new_params[param_name] = var_mapping[param_value_clean]
                    elif self._is_variable_name(param_value_clean):
                        # 看起来像变量但未定义 -> 尝试类型匹配
                        expected_type = self._get_param_type(func_name, param_name)
                        matched_var = self._find_var_by_type(expected_type, type_mapping)
                        
                        if matched_var:
                            new_params[param_name] = matched_var
                        else:
                            # 无法匹配，保留原值
                            new_params[param_name] = param_value
                    else:
                        # 字面量值，保留
                        new_params[param_name] = param_value
                
                # 重构这一行代码
                output_str = ', '.join(new_outputs)
                param_str = ', '.join([f'{k}={v}' for k, v in new_params.items()])
                new_line = f'{output_str} = {func_name}({param_str})'
                
                combined_lines.append(new_line)
                
                # 记录输出变量的类型
                output_types = self._get_output_types(func_name)
                for idx, var_name in enumerate(new_outputs):
                    var_type = output_types.get(idx, 'ANY')
                    type_mapping[var_name] = var_type
        
        return '\n'.join(combined_lines)
    
    def _is_variable_name(self, s: str) -> bool:
        """
        判断字符串是否像变量名
        
        Args:
            s: 字符串
            
        Returns:
            是否像变量名
        """
        return bool(re.match(r'^[a-zA-Z_]\w*$', s))
    
    def _get_param_type(self, func_name: str, param_name: str) -> str:
        """
        获取参数期望的类型
        
        Args:
            func_name: 函数名
            param_name: 参数名
            
        Returns:
            类型字符串
        """
        if func_name not in self.node_defs:
            return 'ANY'
        
        input_params = self.node_defs[func_name].get('input_params', {})
        
        if param_name not in input_params:
            return 'ANY'
        
        param_type = input_params[param_name].get('type', 'ANY')
        
        # 如果是列表类型，取第一个
        if isinstance(param_type, list):
            return param_type[0] if param_type else 'ANY'
        
        return param_type
    
    def _get_output_types(self, func_name: str) -> Dict[int, str]:
        """
        获取函数的输出类型
        
        Args:
            func_name: 函数名
            
        Returns:
            {索引: 类型} 映射
        """
        if func_name not in self.node_defs:
            return {}
        
        output_params = self.node_defs[func_name].get('output_params', {})
        
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
    
    def _find_var_by_type(
        self,
        target_type: str,
        type_mapping: Dict[str, str]
    ) -> Optional[str]:
        """
        根据类型查找最近的变量
        
        Args:
            target_type: 目标类型
            type_mapping: 变量类型映射
            
        Returns:
            变量名或None
        """
        # 从后往前找（最近定义的优先）
        for var_name in reversed(list(type_mapping.keys())):
            var_type = type_mapping[var_name]
            if type_compatible(var_type, target_type):
                return var_name
        
        return None


class CodeToJsonConverter:
    """
    代码转JSON转换器
    使用已有的双向解析器的逻辑，但封装为独立模块
    """
    
    def __init__(self, node_defs: Dict[str, Any]):
        """
        初始化转换器
        
        Args:
            node_defs: 节点定义
        """
        self.node_defs = node_defs
    
    def convert(self, code: str) -> Dict[str, Any]:
        """
        将代码转换为JSON
        
        Args:
            code: 工作流代码
            
        Returns:
            JSON工作流
        """
        nodes = {}
        var_map = {}  # {var_name: (node_id, output_index)}
        node_id_counter = 1
        
        lines = code.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # 解析代码行
            parsed = parse_code_line(line)
            if not parsed:
                continue
            
            func_name = parsed['function']
            outputs = parsed['outputs']
            params = parsed['params']
            
            node_id = str(node_id_counter)
            node_id_counter += 1
            
            # 构建inputs字典
            inputs = {}
            for param_name, param_value in params.items():
                # 去除引号
                param_value_clean = param_value.strip('\'"')
                
                # 检查是否是变量引用
                if param_value_clean in var_map:
                    # 引用其他节点的输出
                    ref_node_id, output_idx = var_map[param_value_clean]
                    inputs[param_name] = [ref_node_id, output_idx]
                else:
                    # 字面量值
                    try:
                        # 尝试解析为JSON值
                        inputs[param_name] = json.loads(param_value)
                    except (json.JSONDecodeError, ValueError):
                        # 保留原始值
                        if param_value.startswith('"') or param_value.startswith("'"):
                            inputs[param_name] = param_value.strip('\'"')
                        else:
                            inputs[param_name] = param_value
            
            # 添加节点
            nodes[node_id] = {
                "inputs": inputs,
                "class_type": func_name
            }
            
            # 记录输出变量
            for idx, var_name in enumerate(outputs):
                var_map[var_name] = (node_id, idx)
        
        return nodes
