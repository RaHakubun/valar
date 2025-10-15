"""
测试代码拆分模块
"""

import pytest
from core.code_splitter import CodeSplitter
from core.data_structures import WorkflowFragment


def test_code_splitter_rule_based(mock_llm_client, sample_workflow_entry, sample_node_defs):
    """测试基于规则的代码拆分"""
    splitter = CodeSplitter(mock_llm_client, sample_node_defs, strategy="rule")
    
    fragments = splitter.split(sample_workflow_entry)
    
    assert len(fragments) > 0
    assert all(isinstance(f, WorkflowFragment) for f in fragments)
    assert all(f.code.strip() != "" for f in fragments)


def test_code_splitter_llm_based(mock_llm_client, sample_workflow_entry, sample_node_defs):
    """测试基于LLM的代码拆分"""
    splitter = CodeSplitter(mock_llm_client, sample_node_defs, strategy="llm")
    
    fragments = splitter.split(sample_workflow_entry)
    
    assert len(fragments) > 0
    # 验证LLM被调用
    assert mock_llm_client.chat.called


def test_code_splitter_hybrid(mock_llm_client, sample_workflow_entry, sample_node_defs):
    """测试混合策略拆分"""
    splitter = CodeSplitter(mock_llm_client, sample_node_defs, strategy="hybrid")
    
    fragments = splitter.split(sample_workflow_entry)
    
    assert len(fragments) > 0


def test_boundary_node_detection(mock_llm_client, sample_node_defs):
    """测试功能边界节点检测"""
    splitter = CodeSplitter(mock_llm_client, sample_node_defs, strategy="rule")
    
    # CheckpointLoader是边界节点
    assert splitter._is_boundary_node("model = CheckpointLoaderSimple()")
    
    # EmptyLatentImage是边界节点
    assert splitter._is_boundary_node("latent = EmptyLatentImage()")
    
    # CLIPTextEncode不是边界节点
    assert not splitter._is_boundary_node("cond = CLIPTextEncode()")


def test_category_inference(mock_llm_client, sample_node_defs):
    """测试类别推断"""
    splitter = CodeSplitter(mock_llm_client, sample_node_defs, strategy="rule")
    
    assert splitter._infer_category_from_line("model = CheckpointLoader()") == "model_loading"
    assert splitter._infer_category_from_line("cond = CLIPTextEncode()") == "text_encoding"
    assert splitter._infer_category_from_line("latent = KSampler()") == "sampling"
    assert splitter._infer_category_from_line("image = VAEDecode()") == "decoding"


def test_fragment_creation(mock_llm_client, sample_node_defs):
    """测试片段创建"""
    splitter = CodeSplitter(mock_llm_client, sample_node_defs, strategy="rule")
    
    code = "model, clip, vae = CheckpointLoaderSimple(ckpt_name=\"model.safetensors\")"
    
    fragment = splitter._create_fragment_from_code(code, "wf_001", "model_loading")
    
    assert fragment.code == code
    assert fragment.source_workflow_id == "wf_001"
    assert fragment.category == "model_loading"
    assert fragment.description != ""


def test_split_empty_workflow(mock_llm_client, sample_workflow_entry, sample_node_defs):
    """测试空工作流拆分"""
    splitter = CodeSplitter(mock_llm_client, sample_node_defs, strategy="rule")
    
    # 创建空工作流
    empty_workflow = sample_workflow_entry
    empty_workflow.workflow_code = ""
    
    fragments = splitter.split(empty_workflow)
    
    # 应该返回空列表
    assert len(fragments) == 0


def test_split_single_line_workflow(mock_llm_client, sample_workflow_entry, sample_node_defs):
    """测试单行工作流拆分"""
    splitter = CodeSplitter(mock_llm_client, sample_node_defs, strategy="rule")
    
    sample_workflow_entry.workflow_code = "model = CheckpointLoaderSimple(ckpt_name=\"model.safetensors\")"
    
    fragments = splitter.split(sample_workflow_entry)
    
    assert len(fragments) == 1
    assert fragments[0].code == sample_workflow_entry.workflow_code
