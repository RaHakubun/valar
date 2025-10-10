"""
工作流验证模块
检查工作流的语法、语义和完整性
"""

from typing import Dict, Any, List, Tuple
from .data_structures import WorkflowFramework
from .llm_client import LLMClient
from .utils import type_compatible
import prompts


class WorkflowValidator:
    """工作流验证器"""
    
    def __init__(
        self,
        node_defs: Dict[str, Any],
        llm_client: Optional[LLMClient] = None
    ):
        """
        初始化验证器
        
        Args:
            node_defs: 节点定义
            llm_client: LLM客户端（用于语义检查）
        """
        self.node_defs = node_defs
        self.llm = llm_client
    
    def validate(
        self,
        framework: WorkflowFramework,
        check_syntax: bool = True,
        check_semantics: bool = True,
        check_completeness: bool = True
    ) -> Tuple[bool, List[str]]:
        """
        验证工作流框架
        
        Args:
            framework: 工作流框架
            check_syntax: 是否检查语法
            check_semantics: 是否检查语义
            check_completeness: 是否检查完整性
            
        Returns:
            (是否有效, 错误列表)
        """
        errors = []
        
        if check_syntax:
            syntax_errors = self._check_syntax(framework)
            errors.extend(syntax_errors)
        
        if check_semantics and self.llm:
            semantic_errors = self._check_semantics(framework)
            errors.extend(semantic_errors)
        
        if check_completeness:
            completeness_errors = self._check_completeness(framework)
            errors.extend(completeness_errors)
        
        is_valid = len(errors) == 0
        
        # 更新框架状态
        framework.is_valid = is_valid
        framework.validation_errors = errors
        
        return is_valid, errors
    
    def _check_syntax(self, framework: WorkflowFramework) -> List[str]:
        """
        语法检查
        
        Args:
            framework: 工作流框架
            
        Returns:
            错误列表
        """
        errors = []
        
        # 检查代码是否为空
        if not framework.framework_code.strip():
            errors.append("工作流代码为空")
            return errors
        
        # 检查是否有有效的代码行
        lines = framework.framework_code.strip().split('\n')
        valid_lines = [l for l in lines if l.strip() and not l.strip().startswith('#')]
        
        if not valid_lines:
            errors.append("没有有效的代码行")
            return errors
        
        # 检查变量定义
        defined_vars = set()
        used_vars = set()
        
        import re
        for line in valid_lines:
            # 提取定义的变量
            var_def_pattern = r'([a-zA-Z_]\w*(?:\s*,\s*[a-zA-Z_]\w*)*)\s*='
            var_def_match = re.match(var_def_pattern, line)
            if var_def_match:
                vars_str = var_def_match.group(1)
                defined_vars.update(v.strip() for v in vars_str.split(','))
            
            # 提取使用的变量
            var_use_pattern = r'([a-zA-Z_]\w*)\s*='
            params = line.split('=', 1)[1] if '=' in line else line
            # 简单匹配（不完美但够用）
            for match in re.finditer(r'\b([a-zA-Z_]\w*)\b', params):
                var_name = match.group(1)
                # 过滤掉函数名和关键字
                if not var_name[0].isupper() and var_name not in ['True', 'False', 'None']:
                    used_vars.add(var_name)
        
        # 检查未定义的变量（简单检查）
        undefined_vars = used_vars - defined_vars
        # 过滤掉可能是参数字符串的
        undefined_vars = {v for v in undefined_vars if len(v) > 1}
        
        if undefined_vars:
            errors.append(f"使用了未定义的变量: {', '.join(list(undefined_vars)[:5])}")
        
        return errors
    
    def _check_semantics(self, framework: WorkflowFramework) -> List[str]:
        """
        语义检查（使用LLM）
        
        Args:
            framework: 工作流框架
            
        Returns:
            错误列表
        """
        if not self.llm:
            return []
        
        errors = []
        
        # 使用LLM检查完整性
        prompt = prompts.WORKFLOW_COMPLETENESS_CHECK_PROMPT.format(
            workflow_code=framework.framework_code
        )
        
        response = self.llm.chat(
            prompt=prompt,
            system_message="你是ComfyUI工作流专家，擅长检查工作流的逻辑完整性。",
            json_mode=True,
            temperature=0.3
        )
        
        parsed = self.llm.parse_json_response(response)
        
        if parsed:
            if not parsed.get('is_complete', True):
                errors.append("工作流不完整")
            
            if not parsed.get('is_reasonable', True):
                errors.append("工作流逻辑不合理")
            
            issues = parsed.get('issues', [])
            errors.extend(issues)
        
        return errors
    
    def _check_completeness(self, framework: WorkflowFramework) -> List[str]:
        """
        完整性检查
        
        Args:
            framework: 工作流框架
            
        Returns:
            错误列表
        """
        errors = []
        
        # 检查是否有输出节点
        has_output = False
        output_nodes = ['SaveImage', 'SaveVideo', 'PreviewImage', 'PreviewVideo']
        
        for node_type in output_nodes:
            if node_type in framework.framework_code:
                has_output = True
                break
        
        if not has_output:
            errors.append("工作流缺少输出节点（SaveImage/PreviewImage等）")
        
        # 检查是否有关键节点
        has_sampler = 'KSampler' in framework.framework_code or 'SamplerCustom' in framework.framework_code
        has_model_loader = 'CheckpointLoader' in framework.framework_code
        
        if not has_sampler and 'Upscale' not in framework.framework_code:
            # 如果不是超分工作流，应该有采样器
            errors.append("生成工作流缺少采样器节点（KSampler）")
        
        if not has_model_loader and 'LoadImage' not in framework.framework_code:
            # 应该有模型加载或图像加载
            errors.append("工作流缺少模型加载节点或图像加载节点")
        
        return errors


class WorkflowJsonValidator:
    """JSON工作流验证器"""
    
    def __init__(self, node_defs: Dict[str, Any]):
        """
        初始化JSON验证器
        
        Args:
            node_defs: 节点定义
        """
        self.node_defs = node_defs
    
    def validate_json(self, workflow_json: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        验证JSON工作流
        
        Args:
            workflow_json: 工作流JSON
            
        Returns:
            (是否有效, 错误列表)
        """
        errors = []
        
        # 1. 检查节点ID唯一性
        node_ids = list(workflow_json.keys())
        if len(node_ids) != len(set(node_ids)):
            errors.append("节点ID不唯一")
        
        # 2. 检查节点类型有效性
        valid_node_types = set(self.node_defs.keys())
        for node_id, node_data in workflow_json.items():
            if not isinstance(node_data, dict):
                errors.append(f"节点 {node_id} 格式错误")
                continue
            
            class_type = node_data.get('class_type')
            if not class_type:
                errors.append(f"节点 {node_id} 缺少class_type")
                continue
            
            if class_type not in valid_node_types:
                errors.append(f"节点 {node_id} 的类型 {class_type} 无效")
        
        # 3. 检查类型兼容性
        type_errors = self._check_type_compatibility(workflow_json)
        errors.extend(type_errors)
        
        # 4. 检查DAG有效性
        if not self._is_valid_dag(workflow_json):
            errors.append("DAG结构无效（可能存在环）")
        
        return len(errors) == 0, errors
    
    def _check_type_compatibility(self, workflow_json: Dict[str, Any]) -> List[str]:
        """
        检查类型兼容性
        
        Args:
            workflow_json: 工作流JSON
            
        Returns:
            错误列表
        """
        errors = []
        
        for node_id, node_data in workflow_json.items():
            if not isinstance(node_data, dict):
                continue
            
            class_type = node_data.get('class_type')
            inputs = node_data.get('inputs', {})
            
            for input_name, input_value in inputs.items():
                # 检查节点连接
                if isinstance(input_value, list) and len(input_value) >= 2:
                    source_node_id = str(input_value[0])
                    output_slot = input_value[1]
                    
                    # 检查源节点是否存在
                    if source_node_id not in workflow_json:
                        errors.append(
                            f"节点 {node_id} 引用了不存在的节点 {source_node_id}"
                        )
                        continue
                    
                    # 获取源节点输出类型
                    source_class_type = workflow_json[source_node_id].get('class_type')
                    source_output_type = self._get_output_type(
                        source_class_type,
                        output_slot
                    )
                    
                    # 获取当前节点输入类型
                    expected_input_type = self._get_input_type(
                        class_type,
                        input_name
                    )
                    
                    # 检查兼容性
                    if source_output_type and expected_input_type:
                        if not type_compatible(source_output_type, expected_input_type):
                            errors.append(
                                f"类型不匹配: 节点 {source_node_id} 输出 {source_output_type}, "
                                f"但节点 {node_id} 的 {input_name} 需要 {expected_input_type}"
                            )
        
        return errors
    
    def _get_output_type(self, class_type: str, output_slot: int) -> Optional[str]:
        """获取输出类型"""
        if class_type not in self.node_defs:
            return None
        
        output_params = self.node_defs[class_type].get('output_params', {})
        
        # 查找对应索引的输出
        for output_key, output_type in output_params.items():
            try:
                key_num = int(output_key.split('_')[-1])
                if key_num == output_slot:
                    return output_type
            except (ValueError, IndexError):
                continue
        
        return None
    
    def _get_input_type(self, class_type: str, input_name: str) -> Optional[str]:
        """获取输入类型"""
        if class_type not in self.node_defs:
            return None
        
        input_params = self.node_defs[class_type].get('input_params', {})
        
        if input_name not in input_params:
            return None
        
        param_type = input_params[input_name].get('type')
        
        if isinstance(param_type, list):
            return param_type[0] if param_type else None
        
        return param_type
    
    def _is_valid_dag(self, workflow_json: Dict[str, Any]) -> bool:
        """
        检查DAG有效性（无环）
        
        Args:
            workflow_json: 工作流JSON
            
        Returns:
            是否有效
        """
        # 构建邻接表
        graph = {node_id: [] for node_id in workflow_json.keys()}
        
        for node_id, node_data in workflow_json.items():
            if not isinstance(node_data, dict):
                continue
            
            inputs = node_data.get('inputs', {})
            for input_value in inputs.values():
                if isinstance(input_value, list) and len(input_value) >= 2:
                    source_node_id = str(input_value[0])
                    if source_node_id in graph:
                        graph[source_node_id].append(node_id)
        
        # DFS检测环
        visited = set()
        rec_stack = set()
        
        def has_cycle(node):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        for node in graph:
            if node not in visited:
                if has_cycle(node):
                    return False
        
        return True
