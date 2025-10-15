"""
测试片段-需求匹配模块
"""

import pytest
from core.fragment_matcher import FragmentMatcher
from core.data_structures import WorkflowFragment, AtomicNeed


def test_fragment_matcher_basic(mock_llm_client, sample_atomic_need):
    """测试基础片段匹配"""
    matcher = FragmentMatcher(mock_llm_client, matching_threshold=0.6)
    
    # 创建一个片段
    fragment = WorkflowFragment(
        fragment_id="frag_1",
        source_workflow_id="wf_001",
        code="latent = KSampler(model=model, positive=cond)",
        description="采样生成图像",
        category="sampling"
    )
    
    # 匹配
    result = matcher.match_fragments_to_needs([fragment], [sample_atomic_need])
    
    assert sample_atomic_need.need_id in result
    # 应该有匹配结果（因为mock返回matched=true）
    assert len(result[sample_atomic_need.need_id]) > 0


def test_fragment_matcher_llm_judge(mock_llm_client):
    """测试LLM判断匹配"""
    matcher = FragmentMatcher(mock_llm_client, use_llm=True)
    
    need = AtomicNeed(
        need_id="need_1",
        description="生成图像",
        category="generation",
        modality="image"
    )
    
    fragment = WorkflowFragment(
        fragment_id="frag_1",
        source_workflow_id="wf_001",
        code="latent = KSampler()",
        description="采样生成",
        category="sampling"
    )
    
    matched, confidence, reason = matcher._llm_judge_match(need, fragment)
    
    # 根据mock的返回
    assert matched == True
    assert confidence == 0.85
    assert "满足" in reason


def test_fragment_matcher_rule_based(mock_llm_client):
    """测试基于规则的匹配"""
    matcher = FragmentMatcher(mock_llm_client, use_llm=False, matching_threshold=0.5)
    
    need = AtomicNeed(
        need_id="need_1",
        description="图像生成 sampling",
        category="generation",
        modality="image"
    )
    
    fragment = WorkflowFragment(
        fragment_id="frag_1",
        source_workflow_id="wf_001",
        code="latent = KSampler()",
        description="采样生成",
        category="generation"
    )
    
    matched, confidence, reason = matcher._rule_based_match(need, fragment)
    
    # 类别匹配应该有较高得分
    assert confidence > 0.5


def test_fragment_matcher_threshold(mock_llm_client):
    """测试匹配阈值"""
    # 高阈值
    matcher_high = FragmentMatcher(mock_llm_client, matching_threshold=0.9, use_llm=False)
    
    need = AtomicNeed(
        need_id="need_1",
        description="测试",
        category="test",
        modality="image"
    )
    
    fragment = WorkflowFragment(
        fragment_id="frag_1",
        source_workflow_id="wf_001",
        code="test = Test()",
        category="different"  # 不同类别
    )
    
    result = matcher_high.match_fragments_to_needs([fragment], [need])
    
    # 高阈值下不应该匹配
    assert len(result[need.need_id]) == 0


def test_category_compatibility(mock_llm_client):
    """测试类别兼容性"""
    matcher = FragmentMatcher(mock_llm_client)
    
    # generation 和 sampling 应该兼容
    assert matcher._category_compatible("generation", "sampling")
    
    # 相同类别应该兼容
    assert matcher._category_compatible("editing", "editing")
    
    # 不相关类别不兼容
    assert not matcher._category_compatible("upscaling", "text_encoding")


def test_keyword_match_score(mock_llm_client):
    """测试关键词匹配得分"""
    matcher = FragmentMatcher(mock_llm_client)
    
    need = AtomicNeed(
        need_id="need_1",
        description="generate image using model",
        category="generation",
        modality="image"
    )
    
    fragment = WorkflowFragment(
        fragment_id="frag_1",
        source_workflow_id="wf_001",
        code="image = Generate(model=model)",
        description="generate image"
    )
    
    score = matcher._keyword_match_score(need, fragment)
    
    # 应该有一定的匹配度（共同关键词：generate, image, model）
    assert score > 0


def test_constraint_match_score(mock_llm_client):
    """测试约束匹配得分"""
    matcher = FragmentMatcher(mock_llm_client)
    
    need = AtomicNeed(
        need_id="need_1",
        description="使用Flux模型",
        category="generation",
        modality="image",
        constraints={"model": "flux"}
    )
    
    fragment = WorkflowFragment(
        fragment_id="frag_1",
        source_workflow_id="wf_001",
        code='model = CheckpointLoader(ckpt_name="flux.safetensors")'
    )
    
    score = matcher._constraint_match_score(need, fragment)
    
    # 代码中包含"flux"，应该匹配
    assert score > 0
