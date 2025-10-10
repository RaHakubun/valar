"""
参数补全模块
为工作流中的占位符和空参数填充合适的值
"""

from typing import Dict, Any, Optional
from .llm_client import LLMClient
import prompts
import random


class ParameterCompleter:
    """参数补全器"""
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        """
        初始化参数补全器
        
        Args:
            llm_client: LLM客户端
        """
        self.llm = llm_client
    
    def complete(
        self,
        workflow_json: Dict[str, Any],
        user_request: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        补全工作流参数
        
        Args:
            workflow_json: 工作流JSON
            user_request: 用户原始需求
            context: 上下文信息（如输入文件路径）
            
        Returns:
            补全后的工作流JSON
        """
        context = context or {}
        
        # 1. 提取需要补全的参数
        if self.llm:
            param_values = self._llm_extract_parameters(user_request)
        else:
            param_values = self._simple_extract_parameters(user_request)
        
        # 2. 补全各类参数
        workflow_json = self._fill_text_prompts(workflow_json, param_values)
        workflow_json = self._fill_file_paths(workflow_json, context)
        workflow_json = self._fill_output_names(workflow_json, context)
        workflow_json = self._fill_default_parameters(workflow_json)
        
        return workflow_json
    
    def _llm_extract_parameters(self, user_request: str) -> Dict[str, Any]:
        """
        使用LLM提取参数值
        
        Args:
            user_request: 用户需求
            
        Returns:
            参数字典
        """
        prompt = prompts.PARAMETER_COMPLETION_PROMPT.format(
            workflow_code="",  # 这里不需要传代码
            user_request=user_request
        )
        
        response = self.llm.chat(
            prompt=prompt,
            system_message="你是ComfyUI工作流专家，擅长从用户需求中提取参数。",
            json_mode=True,
            temperature=0.3
        )
        
        parsed = self.llm.parse_json_response(response)
        
        if parsed and 'parameters' in parsed:
            return parsed['parameters']
        else:
            return self._simple_extract_parameters(user_request)
    
    def _simple_extract_parameters(self, user_request: str) -> Dict[str, Any]:
        """
        简单的参数提取（回退方案）
        
        Args:
            user_request: 用户需求
            
        Returns:
            参数字典
        """
        params = {
            'text': user_request,  # 默认使用完整需求作为提示词
            'width': 1024,
            'height': 1024,
            'steps': 20,
            'cfg': 7.0,
            'sampler_name': 'euler',
            'scheduler': 'normal'
        }
        
        # 简单关键词匹配
        request_lower = user_request.lower()
        
        # 检测尺寸
        if '512' in request_lower:
            params['width'] = params['height'] = 512
        elif '768' in request_lower:
            params['width'] = params['height'] = 768
        elif '2048' in request_lower:
            params['width'] = params['height'] = 2048
        
        # 检测模型
        if 'flux' in request_lower:
            params['ckpt_name'] = 'flux_dev.safetensors'
        elif 'sd3' in request_lower:
            params['ckpt_name'] = 'sd3_medium.safetensors'
        elif 'sdxl' in request_lower:
            params['ckpt_name'] = 'sdxl_base.safetensors'
        else:
            params['ckpt_name'] = 'model.safetensors'
        
        return params
    
    def _fill_text_prompts(
        self,
        workflow_json: Dict[str, Any],
        param_values: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        填充文本提示词
        
        Args:
            workflow_json: 工作流JSON
            param_values: 参数值
            
        Returns:
            填充后的工作流JSON
        """
        prompt_text = param_values.get('text', '')
        
        # 找到所有文本编码节点
        for node_id, node_data in workflow_json.items():
            if not isinstance(node_data, dict):
                continue
            
            class_type = node_data.get('class_type', '')
            
            if class_type in ['CLIPTextEncode', 'CLIPTextEncodeSDXL']:
                inputs = node_data.get('inputs', {})
                
                # 检查text字段
                if 'text' in inputs:
                    current_text = inputs['text']
                    
                    # 如果是空的、占位符或包含{{}}，则填充
                    if (not current_text or 
                        current_text.strip() == '' or
                        '{{' in current_text or
                        current_text == 'prompt'):
                        
                        inputs['text'] = prompt_text
        
        return workflow_json
    
    def _fill_file_paths(
        self,
        workflow_json: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        填充文件路径
        
        Args:
            workflow_json: 工作流JSON
            context: 上下文信息
            
        Returns:
            填充后的工作流JSON
        """
        input_file = context.get('input_file')
        if not input_file:
            return workflow_json
        
        # 找到所有加载节点
        for node_id, node_data in workflow_json.items():
            if not isinstance(node_data, dict):
                continue
            
            class_type = node_data.get('class_type', '')
            
            if class_type in ['LoadImage', 'LoadVideo']:
                inputs = node_data.get('inputs', {})
                
                if 'image' in inputs:
                    inputs['image'] = input_file
                elif 'video' in inputs:
                    inputs['video'] = input_file
        
        return workflow_json
    
    def _fill_output_names(
        self,
        workflow_json: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        填充输出文件名
        
        Args:
            workflow_json: 工作流JSON
            context: 上下文信息
            
        Returns:
            填充后的工作流JSON
        """
        output_prefix = context.get('output_prefix', 'comfyui_output')
        
        # 找到所有保存节点
        for node_id, node_data in workflow_json.items():
            if not isinstance(node_data, dict):
                continue
            
            class_type = node_data.get('class_type', '')
            
            if class_type in ['SaveImage', 'SaveVideo']:
                inputs = node_data.get('inputs', {})
                
                if 'filename_prefix' in inputs:
                    inputs['filename_prefix'] = output_prefix
        
        return workflow_json
    
    def _fill_default_parameters(
        self,
        workflow_json: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        填充默认参数
        
        Args:
            workflow_json: 工作流JSON
            
        Returns:
            填充后的工作流JSON
        """
        # 为采样器设置默认参数
        for node_id, node_data in workflow_json.items():
            if not isinstance(node_data, dict):
                continue
            
            class_type = node_data.get('class_type', '')
            inputs = node_data.get('inputs', {})
            
            if class_type == 'KSampler':
                # seed（如果为空或0，使用随机）
                if 'seed' not in inputs or inputs.get('seed') == 0:
                    inputs['seed'] = random.randint(0, 2**32 - 1)
                
                # steps
                if 'steps' not in inputs:
                    inputs['steps'] = 20
                
                # cfg
                if 'cfg' not in inputs:
                    inputs['cfg'] = 7.0
                
                # sampler_name
                if 'sampler_name' not in inputs:
                    inputs['sampler_name'] = 'euler'
                
                # scheduler
                if 'scheduler' not in inputs:
                    inputs['scheduler'] = 'normal'
                
                # denoise
                if 'denoise' not in inputs:
                    inputs['denoise'] = 1.0
            
            # EmptyLatentImage默认值
            elif class_type == 'EmptyLatentImage':
                if 'width' not in inputs:
                    inputs['width'] = 1024
                if 'height' not in inputs:
                    inputs['height'] = 1024
                if 'batch_size' not in inputs:
                    inputs['batch_size'] = 1
        
        return workflow_json
