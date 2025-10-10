"""
LLM客户端封装
支持OpenAI API调用
"""

import json
from typing import Dict, Any, Optional
import openai


class LLMClient:
    """LLM客户端"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化LLM客户端
        
        Args:
            config: 配置字典
        """
        self.config = config
        openai_config = config.get('openai', {})
        
        # 设置API Key
        openai.api_key = openai_config.get('api_key', '')
        
        # 设置API Base（如果使用代理）
        api_base = openai_config.get('api_base')
        if api_base:
            openai.api_base = api_base
        
        self.chat_model = openai_config.get('chat_model', 'gpt-4-turbo')
        self.temperature = openai_config.get('temperature', 0.7)
        self.max_tokens = openai_config.get('max_tokens', 4096)
        
    def chat(
        self, 
        prompt: str, 
        system_message: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False
    ) -> str:
        """
        调用Chat API
        
        Args:
            prompt: 用户提示
            system_message: 系统消息
            temperature: 温度参数
            max_tokens: 最大token数
            json_mode: 是否使用JSON模式
            
        Returns:
            LLM回复
        """
        messages = []
        
        if system_message:
            messages.append({
                "role": "system",
                "content": system_message
            })
        
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        try:
            kwargs = {
                "model": self.chat_model,
                "messages": messages,
                "temperature": temperature or self.temperature,
                "max_tokens": max_tokens or self.max_tokens,
            }
            
            # GPT-4-turbo及以上支持JSON模式
            if json_mode and 'gpt-4' in self.chat_model:
                kwargs["response_format"] = {"type": "json_object"}
            
            response = openai.ChatCompletion.create(**kwargs)
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"LLM调用失败: {e}")
            return ""
    
    def parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        解析JSON响应
        
        Args:
            response: LLM返回的文本
            
        Returns:
            解析后的JSON对象，失败返回None
        """
        try:
            # 尝试直接解析
            return json.loads(response)
        except json.JSONDecodeError:
            # 尝试提取```json...```块
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
            
            # 尝试提取第一个完整的JSON对象
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass
            
            print(f"无法解析JSON响应: {response[:200]}...")
            return None
    
    def embed(self, text: str) -> Optional[list]:
        """
        生成文本的embedding
        
        Args:
            text: 输入文本
            
        Returns:
            Embedding向量
        """
        embedding_model = self.config.get('openai', {}).get('embedding_model', 'text-embedding-3-large')
        
        try:
            response = openai.Embedding.create(
                model=embedding_model,
                input=text
            )
            return response['data'][0]['embedding']
        except Exception as e:
            print(f"Embedding生成失败: {e}")
            return None
