"""
测试需求分解模块
"""

import pytest
from core.need_decomposer import NeedDecomposer
from core.data_structures import AtomicNeed, DecomposedNeeds


def test_need_decomposer_basic(mock_llm_client):
    """测试基础需求分解"""
    decomposer = NeedDecomposer(mock_llm_client)
    
    user_request = "生成一个粘土风格的人物肖像"
    result = decomposer.decompose(user_request)
    
    assert isinstance(result, DecomposedNeeds)
    assert len(result.atomic_needs) > 0
    assert isinstance(result.atomic_needs[0], AtomicNeed)
    assert result.atomic_needs[0].description != ""


def test_need_decomposer_with_dependencies(mock_llm_client):
    """测试带依赖的需求分解"""
    # 模拟返回多个有依赖关系的需求
    def mock_chat_with_deps(prompt, **kwargs):
        return '''
        {
            "atomic_needs": [
                {
                    "need_id": "need_1",
                    "description": "生成图像",
                    "category": "generation",
                    "modality": "image",
                    "priority": 10,
                    "dependencies": [],
                    "constraints": {}
                },
                {
                    "need_id": "need_2",
                    "description": "超分辨率",
                    "category": "upscaling",
                    "modality": "image",
                    "priority": 5,
                    "dependencies": ["need_1"],
                    "constraints": {"scale": 4}
                }
            ]
        }
        '''
    
    mock_llm_client.chat.side_effect = mock_chat_with_deps
    
    decomposer = NeedDecomposer(mock_llm_client)
    result = decomposer.decompose("生成图像并超分")
    
    assert len(result.atomic_needs) == 2
    assert result.atomic_needs[1].dependencies == ["need_1"]
    assert len(result.execution_order) == 2
    assert result.execution_order[0] == "need_1"  # 无依赖的先执行


def test_need_decomposer_fallback(mock_llm_client):
    """测试LLM失败时的回退机制"""
    # 模拟LLM返回无效响应
    mock_llm_client.chat.return_value = "invalid json"
    mock_llm_client.parse_json_response.return_value = None
    
    decomposer = NeedDecomposer(mock_llm_client)
    result = decomposer.decompose("测试需求")
    
    # 应该使用回退方案，返回单一需求
    assert len(result.atomic_needs) == 1
    assert result.atomic_needs[0].description == "测试需求"


def test_dependency_graph_construction(mock_llm_client):
    """测试依赖图构建"""
    decomposer = NeedDecomposer(mock_llm_client)
    
    needs = [
        AtomicNeed("need_1", "任务1", "gen", "image", dependencies=[]),
        AtomicNeed("need_2", "任务2", "edit", "image", dependencies=["need_1"]),
        AtomicNeed("need_3", "任务3", "upscale", "image", dependencies=["need_2"])
    ]
    
    graph = decomposer._build_dependency_graph(needs)
    
    assert graph["need_1"] == ["need_2"]
    assert graph["need_2"] == ["need_3"]
    assert graph["need_3"] == []


def test_topological_sort(mock_llm_client):
    """测试拓扑排序"""
    decomposer = NeedDecomposer(mock_llm_client)
    
    # 构建一个DAG: 1 -> 2, 1 -> 3, 2 -> 4, 3 -> 4
    graph = {
        "need_1": ["need_2", "need_3"],
        "need_2": ["need_4"],
        "need_3": ["need_4"],
        "need_4": []
    }
    
    order = decomposer._topological_sort(graph)
    
    # need_1 应该在最前面
    assert order[0] == "need_1"
    # need_4 应该在最后
    assert order[-1] == "need_4"
    # need_2 和 need_3 应该在 need_1 之后，need_4 之前
    assert order.index("need_2") > order.index("need_1")
    assert order.index("need_3") > order.index("need_1")
    assert order.index("need_2") < order.index("need_4")
    assert order.index("need_3") < order.index("need_4")


def test_topological_sort_with_cycle(mock_llm_client):
    """测试检测环的情况"""
    decomposer = NeedDecomposer(mock_llm_client)
    
    # 构建一个有环的图: 1 -> 2 -> 3 -> 1
    graph = {
        "need_1": ["need_2"],
        "need_2": ["need_3"],
        "need_3": ["need_1"]
    }
    
    # 应该返回所有节点但不保证顺序
    order = decomposer._topological_sort(graph)
    assert len(order) == 3
