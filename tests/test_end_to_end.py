"""
端到端集成测试
测试完整的生成流程
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json
import os


@pytest.fixture
def mock_config():
    """模拟配置"""
    return {
        'openai': {
            'api_key': 'test_key',
            'embedding_model': 'text-embedding-3-large',
            'chat_model': 'gpt-4-turbo'
        },
        'reranker': {
            'model_name': 'cross-encoder/mmarco-mMiniLMv2-L12-H384-V1'
        },
        'workflow_library': {
            'data_path': './test_data/workflow_library',
            'retrieval': {
                'top_k_rerank': 5
            }
        },
        'code_splitting': {
            'strategy': 'rule'
        },
        'fragment_matching': {
            'matching_threshold': 0.6
        },
        'node_definitions': {
            'yaml_path': './previouswork/nodes.yaml'
        }
    }


def test_simple_workflow_generation(mock_llm_client, mock_config, sample_node_defs, tmp_path):
    """测试简单的工作流生成（不依赖真实API）"""
    
    # 修改临时数据路径
    mock_config['workflow_library']['data_path'] = str(tmp_path / 'workflow_library')
    
    with patch('core.utils.load_config', return_value=mock_config):
        with patch('core.utils.load_node_definitions', return_value=sample_node_defs):
            with patch('core.llm_client.LLMClient', return_value=mock_llm_client):
                with patch('core.vector_search.Reranker'):
                    
                    from generator import ComfyUIWorkflowGenerator
                    
                    # 创建生成器
                    generator = ComfyUIWorkflowGenerator.__new__(ComfyUIWorkflowGenerator)
                    generator.config = mock_config
                    generator.node_defs = sample_node_defs
                    generator.llm_client = mock_llm_client
                    
                    # 模拟向量索引
                    generator.vector_index = Mock()
                    generator.vector_index.search = Mock(return_value=[])
                    
                    # 模拟Reranker
                    generator.reranker = Mock()
                    generator.reranker.rerank = Mock(return_value=[])
                    
                    # 模拟工作流库
                    generator.workflow_library = Mock()
                    generator.workflow_library.workflows = {}
                    
                    # 初始化各个组件
                    from core.need_decomposer import NeedDecomposer
                    from core.code_splitter import CodeSplitter
                    from core.fragment_matcher import FragmentMatcher
                    from core.workflow_assembler import WorkflowAssembler, CodeToJsonConverter
                    from core.validator import WorkflowValidator, WorkflowJsonValidator
                    from core.parameter_completer import ParameterCompleter
                    
                    generator.need_decomposer = NeedDecomposer(mock_llm_client)
                    generator.code_splitter = CodeSplitter(mock_llm_client, sample_node_defs, "rule")
                    generator.fragment_matcher = FragmentMatcher(mock_llm_client, use_llm=False)
                    generator.workflow_assembler = WorkflowAssembler(sample_node_defs)
                    generator.code_to_json_converter = CodeToJsonConverter(sample_node_defs)
                    generator.validator = WorkflowValidator(sample_node_defs, mock_llm_client)
                    generator.json_validator = WorkflowJsonValidator(sample_node_defs)
                    generator.parameter_completer = ParameterCompleter(mock_llm_client)
                    
                    # 模拟检索器
                    generator.retriever = Mock()
                    
                    # 创建模拟工作流
                    from core.data_structures import WorkflowEntry, WorkflowIntent, WorkflowComplexity
                    
                    mock_workflow = WorkflowEntry(
                        workflow_id="wf_test",
                        workflow_json={},
                        workflow_code="""
model, clip, vae = CheckpointLoaderSimple(ckpt_name="model.safetensors")
conditioning = CLIPTextEncode(clip=clip, text="test")
latent = EmptyLatentImage(width=512, height=512, batch_size=1)
sampled = KSampler(model=model, positive=conditioning, latent_image=latent, seed=42, steps=20)
image = VAEDecode(samples=sampled, vae=vae)
output = SaveImage(images=image, filename_prefix="output")
                        """.strip(),
                        intent=WorkflowIntent(
                            task="text-to-image",
                            description="生成图像",
                            keywords=["生成"],
                            modality="image",
                            operation="generation"
                        ),
                        complexity=WorkflowComplexity.VANILLA,
                        node_count=6
                    )
                    
                    generator.retriever.retrieve_for_all_needs = Mock(
                        return_value={"need_1": [mock_workflow]}
                    )
                    
                    # 执行生成
                    try:
                        result = generator.generate("生成一个图像", save_intermediate=False)
                        
                        # 验证结果
                        assert isinstance(result, dict)
                        assert len(result) > 0
                        
                        # 检查是否有基本节点
                        has_sampler = any(
                            node.get('class_type') == 'KSampler' 
                            for node in result.values() 
                            if isinstance(node, dict)
                        )
                        
                        print(f"生成成功，包含 {len(result)} 个节点")
                        print(f"包含采样器: {has_sampler}")
                        
                    except Exception as e:
                        pytest.fail(f"生成失败: {e}")


def test_workflow_with_context(mock_llm_client, mock_config, sample_node_defs, tmp_path):
    """测试带上下文的工作流生成"""
    
    mock_config['workflow_library']['data_path'] = str(tmp_path / 'workflow_library')
    
    context = {
        'input_file': 'test_image.png',
        'output_prefix': 'test_output'
    }
    
    # 类似上面的测试，但传入context
    # 验证参数补全是否正确应用了context
    
    from core.parameter_completer import ParameterCompleter
    
    completer = ParameterCompleter(mock_llm_client)
    
    test_workflow = {
        "1": {
            "inputs": {"image": "placeholder"},
            "class_type": "LoadImage"
        },
        "2": {
            "inputs": {"images": ["1", 0], "filename_prefix": "placeholder"},
            "class_type": "SaveImage"
        }
    }
    
    result = completer.complete(test_workflow, "测试", context)
    
    # 验证文件路径被填充
    assert result["1"]["inputs"]["image"] == "test_image.png"
    assert result["2"]["inputs"]["filename_prefix"] == "test_output"


def test_validation_catches_errors(sample_node_defs):
    """测试验证器能捕获错误"""
    from core.validator import WorkflowJsonValidator
    
    validator = WorkflowJsonValidator(sample_node_defs)
    
    # 创建一个有问题的工作流（引用不存在的节点）
    invalid_workflow = {
        "1": {
            "inputs": {"model": ["999", 0]},  # 节点999不存在
            "class_type": "KSampler"
        }
    }
    
    is_valid, errors = validator.validate_json(invalid_workflow)
    
    assert not is_valid
    assert len(errors) > 0
    assert any("不存在" in error or "999" in error for error in errors)


def test_full_pipeline_mock(mock_llm_client, sample_node_defs):
    """测试完整流程的各个阶段"""
    
    # 阶段1: 需求分解
    from core.need_decomposer import NeedDecomposer
    
    decomposer = NeedDecomposer(mock_llm_client)
    decomposed = decomposer.decompose("生成图像")
    
    assert len(decomposed.atomic_needs) > 0
    
    # 阶段2: 代码拆分
    from core.code_splitter import CodeSplitter
    from core.data_structures import WorkflowEntry, WorkflowIntent, WorkflowComplexity
    
    test_workflow = WorkflowEntry(
        workflow_id="test",
        workflow_json={},
        workflow_code="model = CheckpointLoaderSimple(ckpt_name=\"model.safetensors\")",
        intent=WorkflowIntent("test", "test", [], "image", "generation"),
        complexity=WorkflowComplexity.VANILLA,
        node_count=1
    )
    
    splitter = CodeSplitter(mock_llm_client, sample_node_defs, "rule")
    fragments = splitter.split(test_workflow)
    
    assert len(fragments) > 0
    
    # 阶段3: 片段匹配
    from core.fragment_matcher import FragmentMatcher
    
    matcher = FragmentMatcher(mock_llm_client, use_llm=False)
    mapping = matcher.match_fragments_to_needs(fragments, decomposed.atomic_needs)
    
    assert isinstance(mapping, dict)
    
    # 阶段4: 拼接
    from core.workflow_assembler import WorkflowAssembler
    
    assembler = WorkflowAssembler(sample_node_defs)
    
    if any(len(frags) > 0 for frags in mapping.values()):
        # 如果有匹配的片段
        selected_fragments = []
        for need_id in decomposed.execution_order:
            frags = mapping.get(need_id, [])
            if frags:
                selected_fragments.append(frags[0])
        
        if selected_fragments:
            framework = assembler.assemble(
                selected_fragments,
                decomposed.atomic_needs,
                decomposed.execution_order
            )
            
            assert framework is not None
            assert framework.framework_code != ""
            
            # 阶段5: 转换为JSON
            from core.workflow_assembler import CodeToJsonConverter
            
            converter = CodeToJsonConverter(sample_node_defs)
            workflow_json = converter.convert(framework.framework_code)
            
            assert isinstance(workflow_json, dict)
            assert len(workflow_json) > 0
