"""
LLM客户端封装
支持OpenAI API调用和Gemini Embedding API
"""

import json
import http.client
import urllib.parse
from typing import Dict, Any, Optional
import openai

# 检查OpenAI版本以处理API兼容性
if hasattr(openai, '__version__') and ('1.' in openai.__version__ or '2.' in openai.__version__):
    # OpenAI v1.x+ or v2.x+ 使用新API
    from openai import OpenAI
else:
    # OpenAI v0.x 使用旧API
    OpenAI = None


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
        
        # 初始化OpenAI客户端 - 根据版本处理兼容性
        if OpenAI is not None:
            # 使用新API (v1.x+)
            self.openai_client = OpenAI(
                api_key=openai_config.get('api_key', ''),
                base_url=openai_config.get('api_base', 'https://api.openai.com/v1')
            )
            self.use_new_api = True
        else:
            # 使用旧API (v0.x)
            openai.api_key = openai_config.get('api_key', '')
            api_base = openai_config.get('api_base')
            if api_base:
                openai.api_base = api_base
            self.use_new_api = False
        
        self.chat_model = openai_config.get('chat_model', 'gpt-4-turbo')
        self.temperature = openai_config.get('temperature', 0.7)
        self.max_tokens = openai_config.get('max_tokens', 4096)
        
        # 检查是否有Gemini配置
        self.gemini_config = config.get('gemini', {})
        self.use_gemini_embedding = bool(self.gemini_config.get('api_key'))
        
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
            if self.use_new_api:
                # 使用新API (v1.x+)
                kwargs = {
                    "model": self.chat_model,
                    "messages": messages,
                    "temperature": temperature or self.temperature,
                    "max_tokens": max_tokens or self.max_tokens,
                }
                
                # GPT-4-turbo及以上支持JSON模式
                if json_mode and 'gpt-4' in self.chat_model:
                    kwargs["response_format"] = {"type": "json_object"}
                
                response = self.openai_client.chat.completions.create(**kwargs)
                
                return response.choices[0].message.content
            else:
                # 使用旧API (v0.x)
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
        # 优先使用Gemini API（如果配置了）
        if self.use_gemini_embedding:
            return self._embed_with_gemini(text)
        else:
            # 使用OpenAI API
            return self._embed_with_openai(text)
    
    def _embed_with_openai(self, text: str) -> Optional[list]:
        """
        使用OpenAI API生成embedding
        
        Args:
            text: 输入文本
            
        Returns:
            Embedding向量
        """
        embedding_model = self.config.get('openai', {}).get('embedding_model', 'text-embedding-3-large')
        
        try:
            if self.use_new_api:
                # 新API
                response = self.openai_client.embeddings.create(
                    model=embedding_model,
                    input=text
                )
                return response.data[0].embedding
            else:
                # 旧API
                response = openai.Embedding.create(
                    model=embedding_model,
                    input=text
                )
                return response['data'][0]['embedding']
        except Exception as e:
            print(f"OpenAI Embedding生成失败: {e}")
            return None
    
    def _embed_with_gemini(self, text: str) -> Optional[list]:
        """
        使用Gemini API生成embedding
        
        Args:
            text: 输入文本
            
        Returns:
            Embedding向量
        """
        try:
            # 获取Gemini配置
            api_key = self.gemini_config.get('api_key', '')
            api_base = self.gemini_config.get('api_base', 'https://xiaoai.plus/v1')
            embedding_model = self.gemini_config.get('embedding_model', 'gemini-embedding-001')
            
            if not api_key:
                print("Gemini API密钥未配置")
                return None
            
            # 解析API端点
            import urllib.parse
            parsed_url = urllib.parse.urlparse(api_base)
            host = parsed_url.netloc
            path = parsed_url.path if parsed_url.path else '/v1/embeddings'
            
            # 准备请求
            import json
            payload = json.dumps({
                "input": text,
                "model": embedding_model,
                "encoding_format": "float"
            })
            
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            # 发送请求
            conn = http.client.HTTPSConnection(host)
            conn.request("POST", path, payload, headers)
            res = conn.getresponse()
            data = res.read()
            conn.close()
            
            response_json = json.loads(data.decode("utf-8"))
            
            if 'data' in response_json and len(response_json['data']) > 0:
                return response_json['data'][0]['embedding']
            else:
                print(f"Gemini API返回格式错误: {response_json}")
                return None
                
        except Exception as e:
            print(f"Gemini Embedding生成失败: {e}")
            return None
