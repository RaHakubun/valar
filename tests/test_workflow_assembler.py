"""
测试工作流拼接模块
"""

import pytest
from core.workflow_assembler import WorkflowAssembler, CodeToJsonConverter
from core.data_structures import WorkflowFragment, AtomicNeed


def test_workflow_assembler_basic(sample_node_defs):
    """测试基础工作流拼接"""
    assembler = WorkflowAssembler(sample_node_defs)
    
    # 创建两个片段
    fragment1 = WorkflowFragment(
        fragment_id="frag_1",
        source_workflow_id="wf_001",
        code="model, clip, vae = CheckpointLoaderSimple(ckpt_name=\"model.safetensors\")",
        mapped_need_id="need_1",
        match_confidence=0.9
    )
    
    fragment2 = WorkflowFragment(
        fragment_id="frag_2",
        source_workflow_id="wf_002",
        code="conditioning = CLIPTextEncode(clip=clip, text=\"test\")",
        mapped_need_id="need_2",
        match_confidence=0.8
    )
    
    needs = [
        AtomicNeed("need_1", "加载模型", "model_loading", "image"),
        AtomicNeed("need_2", "文本编码", "text_encoding", "image", dependencies=["need_1"])
    ]
    
    framework = assembler.assemble([fragment1, fragment2], needs, ["need_1", "need_2"])
    
    assert framework is not None
    assert len(framework.fragments) == 2
    assert framework.framework_code != ""


def test_combine_code_fragments(sample_node_defs):
    """测试代码片段组合"""
    assembler = WorkflowAssembler(sample_node_defs)
    
    fragment1 = WorkflowFragment(
        fragment_id="frag_1",
        source_workflow_id="wf_001",
        code="model, clip, vae = CheckpointLoaderSimple(ckpt_name=\"model.safetensors\")",
        mapped_need_id="need_1"
    )
    
    fragment2 = WorkflowFragment(
        fragment_id="frag_2",
        source_workflow_id="wf_001",
        code="conditioning = CLIPTextEncode(clip=clip, text=\"prompt\")",
        mapped_need_id="need_2"
    )
    
    combined = assembler._combine_code_fragments([fragment1, fragment2])
    
    # 应该包含两个片段的代码
    assert "CheckpointLoaderSimple" in combined
    assert "CLIPTextEncode" in combined
    # 变量应该被重命名为var_X
    assert "var_" in combined


def test_variable_renaming(sample_node_defs):
    """测试变量重命名避免冲突"""
    assembler = WorkflowAssembler(sample_node_defs)
    
    # 两个片段都定义了model变量
    fragment1 = WorkflowFragment(
        fragment_id="frag_1",
        source_workflow_id="wf_001",
        code="model = CheckpointLoaderSimple(ckpt_name=\"model1.safetensors\")",
        mapped_need_id="need_1"
    )
    
    fragment2 = WorkflowFragment(
        fragment_id="frag_2",
        source_workflow_id="wf_002",
        code="model = CheckpointLoaderSimple(ckpt_name=\"model2.safetensors\")",
        mapped_need_id="need_2"
    )
    
    combined = assembler._combine_code_fragments([fragment1, fragment2])
    
    # 应该有不同的变量名
    lines = combined.split('\n')
    var_names = [line.split('=')[0].strip() for line in lines if '=' in line]
    
    # 不应该有重复的变量名
    assert len(var_names) == len(set(var_names))


def test_code_to_json_converter(sample_node_defs, sample_workflow_code):
    """测试代码转JSON"""
    converter = CodeToJsonConverter(sample_node_defs)
    
    workflow_json = converter.convert(sample_workflow_code)
    
    assert isinstance(workflow_json, dict)
    assert len(workflow_json) > 0
    
    # 检查节点结构
    for node_id, node_data in workflow_json.items():
        assert "inputs" in node_data
        assert "class_type" in node_data


def test_code_to_json_with_references(sample_node_defs):
    """测试带引用的代码转JSON"""
    converter = CodeToJsonConverter(sample_node_defs)
    
    code = """
var_1, var_2, var_3 = CheckpointLoaderSimple(ckpt_name="model.safetensors")
var_4 = CLIPTextEncode(clip=var_2, text="prompt")
    """.strip()
    
    workflow_json = converter.convert(code)
    
    # 检查节点2的clip输入应该引用节点1
    node_2 = workflow_json["2"]
    assert node_2["inputs"]["clip"] == ["1", 1]  # [node_id, output_index]


def test_type_finding(sample_node_defs):
    """测试根据类型查找变量"""
    assembler = WorkflowAssembler(sample_node_defs)
    
    type_mapping = {
        "var_1": "MODEL",
        "var_2": "CLIP",
        "var_3": "VAE"
    }
    
    # 查找CLIP类型
    found = assembler._find_var_by_type("CLIP", type_mapping)
    assert found == "var_2"
    
    # 查找不存在的类型
    found = assembler._find_var_by_type("UNKNOWN", type_mapping)
    assert found is None


def test_get_output_types(sample_node_defs):
    """测试获取输出类型"""
    assembler = WorkflowAssembler(sample_node_defs)
    
    output_types = assembler._get_output_types("CheckpointLoaderSimple")
    
    assert 0 in output_types
    assert output_types[0] == "MODEL"
    assert output_types[1] == "CLIP"
    assert output_types[2] == "VAE"


def test_get_param_type(sample_node_defs):
    """测试获取参数类型"""
    assembler = WorkflowAssembler(sample_node_defs)
    
    param_type = assembler._get_param_type("CLIPTextEncode", "clip")
    assert param_type == "CLIP"
    
    param_type = assembler._get_param_type("CLIPTextEncode", "text")
    assert param_type == "STRING"
