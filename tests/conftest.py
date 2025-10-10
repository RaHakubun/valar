"""
pytest配置文件
提供共享的fixture
"""

import pytest
import sys
import os
from unittest.mock import Mock, MagicMock

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


@pytest.fixture
def mock_llm_client():
    """模拟LLM客户端"""
    client = Mock()
    
    # 模拟chat方法
    def mock_chat(prompt, **kwargs):
        if "需求分解" in prompt or "分解用户需求" in prompt:
            return '''
            {
                "atomic_needs": [
                    {
                        "need_id": "need_1",
                        "description": "生成粘土风格人物肖像",
                        "category": "generation",
                        "modality": "image",
                        "priority": 10,
                        "dependencies": [],
                        "constraints": {"style": "clay", "subject": "portrait"}
                    }
                ]
            }
            '''
        elif "代码片段" in prompt and "拆分" in prompt:
            return '''
            {
                "fragments": [
                    {
                        "fragment_id": "frag_1",
                        "description": "加载模型",
                        "category": "model_loading",
                        "code": "model, clip, vae = CheckpointLoaderSimple(ckpt_name=\\"model.safetensors\\")",
                        "inputs": {},
                        "outputs": {"MODEL": "model", "CLIP": "clip", "VAE": "vae"}
                    }
                ]
            }
            '''
        elif "是否能满足" in prompt or "匹配" in prompt:
            return '''
            {
                "matched": true,
                "confidence": 0.85,
                "reason": "该片段能够满足需求"
            }
            '''
        elif "意图" in prompt:
            return '''
            {
                "task": "text-to-image",
                "modality": "image",
                "operation": "generation",
                "keywords": ["文本", "图像", "生成"],
                "description": "文本生成图像工作流"
            }
            '''
        else:
            return '{"result": "success"}'
    
    client.chat = Mock(side_effect=mock_chat)
    
    # 模拟parse_json_response
    def mock_parse_json(response):
        import json
        try:
            return json.loads(response)
        except:
            return None
    
    client.parse_json_response = Mock(side_effect=mock_parse_json)
    
    # 模拟embed方法
    client.embed = Mock(return_value=[0.1] * 3072)
    
    return client


@pytest.fixture
def sample_workflow_json():
    """示例工作流JSON"""
    return {
        "1": {
            "inputs": {"ckpt_name": "flux_dev.safetensors"},
            "class_type": "CheckpointLoaderSimple"
        },
        "2": {
            "inputs": {"clip": ["1", 1], "text": "beautiful portrait"},
            "class_type": "CLIPTextEncode"
        },
        "3": {
            "inputs": {"width": 1024, "height": 1024, "batch_size": 1},
            "class_type": "EmptyLatentImage"
        },
        "4": {
            "inputs": {
                "model": ["1", 0],
                "positive": ["2", 0],
                "latent_image": ["3", 0],
                "seed": 42,
                "steps": 20
            },
            "class_type": "KSampler"
        },
        "5": {
            "inputs": {"samples": ["4", 0], "vae": ["1", 2]},
            "class_type": "VAEDecode"
        },
        "6": {
            "inputs": {"images": ["5", 0], "filename_prefix": "output"},
            "class_type": "SaveImage"
        }
    }


@pytest.fixture
def sample_workflow_code():
    """示例工作流代码"""
    return """
model, clip, vae = CheckpointLoaderSimple(ckpt_name="flux_dev.safetensors")
conditioning = CLIPTextEncode(clip=clip, text="beautiful portrait")
latent_empty = EmptyLatentImage(width=1024, height=1024, batch_size=1)
latent = KSampler(model=model, positive=conditioning, latent_image=latent_empty, seed=42, steps=20)
image = VAEDecode(samples=latent, vae=vae)
output = SaveImage(images=image, filename_prefix="output")
    """.strip()


@pytest.fixture
def sample_node_defs():
    """示例节点定义"""
    return {
        "CheckpointLoaderSimple": {
            "input_params": {
                "ckpt_name": {"type": "STRING", "default": "model.safetensors"}
            },
            "output_params": {
                "output_0": "MODEL",
                "output_1": "CLIP",
                "output_2": "VAE"
            }
        },
        "CLIPTextEncode": {
            "input_params": {
                "clip": {"type": "CLIP"},
                "text": {"type": "STRING", "default": ""}
            },
            "output_params": {
                "output_0": "CONDITIONING"
            }
        },
        "EmptyLatentImage": {
            "input_params": {
                "width": {"type": "INT", "default": 512},
                "height": {"type": "INT", "default": 512},
                "batch_size": {"type": "INT", "default": 1}
            },
            "output_params": {
                "output_0": "LATENT"
            }
        },
        "KSampler": {
            "input_params": {
                "model": {"type": "MODEL"},
                "positive": {"type": "CONDITIONING"},
                "latent_image": {"type": "LATENT"},
                "seed": {"type": "INT", "default": 0},
                "steps": {"type": "INT", "default": 20}
            },
            "output_params": {
                "output_0": "LATENT"
            }
        },
        "VAEDecode": {
            "input_params": {
                "samples": {"type": "LATENT"},
                "vae": {"type": "VAE"}
            },
            "output_params": {
                "output_0": "IMAGE"
            }
        },
        "SaveImage": {
            "input_params": {
                "images": {"type": "IMAGE"},
                "filename_prefix": {"type": "STRING", "default": "output"}
            },
            "output_params": {}
        }
    }


@pytest.fixture
def sample_atomic_need():
    """示例原子需求"""
    from core.data_structures import AtomicNeed
    return AtomicNeed(
        need_id="need_1",
        description="生成粘土风格人物肖像",
        category="generation",
        modality="image",
        priority=10,
        dependencies=[],
        constraints={"style": "clay", "subject": "portrait"}
    )


@pytest.fixture
def sample_workflow_entry(sample_workflow_json, sample_workflow_code):
    """示例工作流条目"""
    from core.data_structures import WorkflowEntry, WorkflowIntent, WorkflowComplexity
    
    intent = WorkflowIntent(
        task="text-to-image",
        description="基础的文本生成图像工作流",
        keywords=["文本", "图像", "生成"],
        modality="image",
        operation="generation"
    )
    
    return WorkflowEntry(
        workflow_id="wf_test_001",
        workflow_json=sample_workflow_json,
        workflow_code=sample_workflow_code,
        intent=intent,
        intent_embedding=[0.1] * 3072,
        source="test",
        complexity=WorkflowComplexity.VANILLA,
        tags=["test", "basic"],
        node_count=6
    )
