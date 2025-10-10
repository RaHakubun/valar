"""
代码拆分模块
使用LLM提示词进行代码拆分（参考ComfyBench的思路）
也支持简单的基于规则的拆分作为补充
"""

from typing import List, Dict, Any
from .data_structures import WorkflowFragment, WorkflowEntry
from .llm_client import LLMClient
from .utils import generate_fragment_id, extract_node_types_from_code, analyze_code_fragment_io
import prompts


class CodeSplitter:
    """代码拆分器"""
    
    def __init__(self, llm_client: LLMClient, node_defs: Dict[str, Any], strategy: str = "hybrid"):
        """
        初始化代码拆分器
        
        Args:
            llm_client: LLM客户端
            node_defs: 节点定义
            strategy: 拆分策略 ("llm" / "rule" / "hybrid")
        """
        self.llm = llm_client
        self.node_defs = node_defs
        self.strategy = strategy
    
    def split(self, workflow: WorkflowEntry) -> List[WorkflowFragment]:
        """
        拆分工作流为片段
        
        Args:
            workflow: 工作流条目
            
        Returns:
            片段列表
        """
        if self.strategy == "llm":
            return self._split_by_llm(workflow)
        elif self.strategy == "rule":
            return self._split_by_rule(workflow)
        else:  # hybrid
            return self._split_hybrid(workflow)
    
    def _split_by_llm(self, workflow: WorkflowEntry) -> List[WorkflowFragment]:
        """
        使用LLM拆分代码
        
        Args:
            workflow: 工作流条目
            
        Returns:
            片段列表
        """
        # 构建提示词
        node_types = extract_node_types_from_code(workflow.workflow_code)
        
        prompt = prompts.CODE_SPLITTING_PROMPT.format(
            workflow_code=workflow.workflow_code
        )
        
        # 调用LLM
        response = self.llm.chat(
            prompt=prompt,
            system_message="你是ComfyUI工作流专家，擅长代码分析和拆分。",
            json_mode=True
        )
        
        # 解析响应
        parsed = self.llm.parse_json_response(response)
        if not parsed or 'fragments' not in parsed:
            print("LLM拆分失败，回退到规则拆分")
            return self._split_by_rule(workflow)
        
        # 构建Fragment对象
        fragments = []
        for frag_data in parsed['fragments']:
            fragment = WorkflowFragment(
                fragment_id=frag_data.get('fragment_id', generate_fragment_id()),
                source_workflow_id=workflow.workflow_id,
                code=frag_data.get('code', ''),
                description=frag_data.get('description', ''),
                category=frag_data.get('category', 'unknown'),
                inputs=frag_data.get('inputs', {}),
                outputs=frag_data.get('outputs', {})
            )
            fragments.append(fragment)
        
        return fragments
    
    def _split_by_rule(self, workflow: WorkflowEntry) -> List[WorkflowFragment]:
        """
        使用规则拆分代码（简单按语句拆分）
        
        Args:
            workflow: 工作流条目
            
        Returns:
            片段列表
        """
        lines = workflow.workflow_code.strip().split('\n')
        fragments = []
        
        current_fragment_lines = []
        current_category = "unknown"
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # 判断是否是新功能的开始
            is_boundary = self._is_boundary_node(line)
            
            if is_boundary and current_fragment_lines:
                # 保存当前片段
                fragment_code = '\n'.join(current_fragment_lines)
                fragment = self._create_fragment_from_code(
                    fragment_code,
                    workflow.workflow_id,
                    current_category
                )
                fragments.append(fragment)
                
                # 开始新片段
                current_fragment_lines = [line]
                current_category = self._infer_category_from_line(line)
            else:
                # 继续当前片段
                current_fragment_lines.append(line)
                if not current_category or current_category == "unknown":
                    current_category = self._infer_category_from_line(line)
        
        # 保存最后一个片段
        if current_fragment_lines:
            fragment_code = '\n'.join(current_fragment_lines)
            fragment = self._create_fragment_from_code(
                fragment_code,
                workflow.workflow_id,
                current_category
            )
            fragments.append(fragment)
        
        return fragments
    
    def _split_hybrid(self, workflow: WorkflowEntry) -> List[WorkflowFragment]:
        """
        混合策略：先用规则粗拆，如果片段太大再用LLM细拆
        
        Args:
            workflow: 工作流条目
            
        Returns:
            片段列表
        """
        # 先用规则拆分
        fragments = self._split_by_rule(workflow)
        
        # 对于过大的片段，用LLM进一步拆分
        refined_fragments = []
        for fragment in fragments:
            line_count = len(fragment.code.split('\n'))
            
            if line_count > 5:  # 如果片段超过5行，尝试用LLM细拆
                # 创建临时workflow对象
                temp_workflow = WorkflowEntry(
                    workflow_id=workflow.workflow_id,
                    workflow_json={},
                    workflow_code=fragment.code,
                    intent=workflow.intent
                )
                
                sub_fragments = self._split_by_llm(temp_workflow)
                
                if len(sub_fragments) > 1:
                    # LLM成功拆分
                    refined_fragments.extend(sub_fragments)
                else:
                    # LLM拆分失败或只有一个片段，保留原片段
                    refined_fragments.append(fragment)
            else:
                refined_fragments.append(fragment)
        
        return refined_fragments
    
    def _is_boundary_node(self, line: str) -> bool:
        """
        判断是否是功能边界节点
        
        Args:
            line: 代码行
            
        Returns:
            是否是边界
        """
        boundary_nodes = [
            'CheckpointLoaderSimple',
            'CheckpointLoader',
            'LoraLoader',
            'EmptyLatentImage',
            'LoadImage',
            'UpscaleModelLoader',
            'ControlNetLoader',
            'VAELoader',
            'CLIPLoader',
        ]
        
        for node in boundary_nodes:
            if node in line and '=' in line:
                return True
        
        return False
    
    def _infer_category_from_line(self, line: str) -> str:
        """
        从代码行推断功能类别
        
        Args:
            line: 代码行
            
        Returns:
            类别
        """
        if 'CheckpointLoader' in line or 'LoraLoader' in line:
            return 'model_loading'
        elif 'CLIPTextEncode' in line:
            return 'text_encoding'
        elif 'EmptyLatentImage' in line or 'LoadImage' in line:
            return 'image_initialization'
        elif 'KSampler' in line:
            return 'sampling'
        elif 'VAEDecode' in line:
            return 'decoding'
        elif 'VAEEncode' in line:
            return 'encoding'
        elif 'Upscale' in line or 'ImageScale' in line:
            return 'upscaling'
        elif 'ControlNet' in line:
            return 'controlnet'
        elif 'SaveImage' in line or 'PreviewImage' in line:
            return 'output'
        else:
            return 'unknown'
    
    def _create_fragment_from_code(
        self,
        code: str,
        source_workflow_id: str,
        category: str
    ) -> WorkflowFragment:
        """
        从代码创建片段对象
        
        Args:
            code: 代码
            source_workflow_id: 来源工作流ID
            category: 类别
            
        Returns:
            片段对象
        """
        # 分析输入输出
        inputs, outputs = analyze_code_fragment_io(code, self.node_defs)
        
        # 生成描述（简单规则）
        description = self._generate_simple_description(code, category)
        
        return WorkflowFragment(
            fragment_id=generate_fragment_id(),
            source_workflow_id=source_workflow_id,
            code=code,
            description=description,
            category=category,
            inputs=inputs,
            outputs=outputs
        )
    
    def _generate_simple_description(self, code: str, category: str) -> str:
        """
        生成简单的描述
        
        Args:
            code: 代码
            category: 类别
            
        Returns:
            描述
        """
        category_descriptions = {
            'model_loading': '加载模型',
            'text_encoding': '文本编码',
            'image_initialization': '图像初始化',
            'sampling': '采样生成',
            'decoding': '图像解码',
            'encoding': '图像编码',
            'upscaling': '图像超分',
            'controlnet': 'ControlNet处理',
            'output': '保存输出'
        }
        
        base_desc = category_descriptions.get(category, '未知功能')
        
        # 尝试从代码中提取更多信息
        if 'Flux' in code:
            base_desc += '（Flux模型）'
        elif 'SDXL' in code:
            base_desc += '（SDXL模型）'
        
        return base_desc
