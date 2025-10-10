import re
import json
from typing import Dict, Any, List, Tuple

def parse_code_to_dag(code: str) -> Dict[str, Any]:
    """将生成的代码解析回DAG JSON结构"""
    # 定义正则表达式模式
    var_pattern = r'var_(\d+)\s*=\s*([^(\s]+|".*?")\('
    param_pattern = r'(\w+)\s*=\s*((?:[^,"\[\]]|"[^"]*"|\[[^\]]*\])+)'
    
    # 解析每一行代码
    nodes = {}
    var_map = {}  # 跟踪变量对应的节点ID
    
    lines = code.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
            
        # 匹配变量定义行
        var_match = re.match(var_pattern, line)
        if var_match:
            node_id = var_match.group(1)
            func_name = var_match.group(2).strip('"')  # 移除函数名周围的引号
            var_map[f"var_{node_id}"] = node_id
            
            # 提取参数部分
            params_start = line.index('(') + 1
            params_end = line.rindex(')')
            params_str = line[params_start:params_end].strip()
            
            # 解析参数
            inputs = {}
            param_strs = []
            
            # 处理复杂参数（如包含逗号的字符串）
            current_param = ""
            in_quote = False
            bracket_count = 0
            
            for char in params_str:
                if char == '"':
                    in_quote = not in_quote
                elif char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
                elif char == ',' and not in_quote and bracket_count == 0:
                    param_strs.append(current_param.strip())
                    current_param = ""
                    continue
                    
                current_param += char
                
            if current_param:
                param_strs.append(current_param.strip())
            
            # 解析每个参数
            for param_str in param_strs:
                param_match = re.match(param_pattern, param_str)
                if param_match:
                    key = param_match.group(1)
                    value_str = param_match.group(2).strip()
                    
                    # 处理引用类型参数
                    ref_match = re.match(r'var_(\d+)(?:\[(\d+)\])?', value_str)
                    if ref_match:
                        ref_node_id = ref_match.group(1)
                        output_idx = int(ref_match.group(2) or 0)
                        inputs[key] = [ref_node_id, output_idx]
                    else:
                        # 尝试解析为JSON值
                        try:
                            value = json.loads(value_str)
                        except json.JSONDecodeError:
                            # 如果解析失败，作为字符串处理（保留引号）
                            value = value_str
                        inputs[key] = value
            
            # 添加到节点定义
            nodes[node_id] = {
                "inputs": inputs,
                "class_type": func_name
            }
    
    return nodes

# 示例使用
if __name__ == "__main__":
    generated_code = """
var_1 = CheckpointLoaderSimple(ckpt_name="AnimateDiff.safetensors")
var_2 = CLIPLoader(clip_name="clip_vit_l_14.safetensors", type="animatediff", device="default")
var_3 = CLIPTextEncode(text="a cat running through a green meadow with flowers", clip=var_2)
var_4 = CLIPTextEncode(text="blurry, low quality, distorted", clip=var_2)
var_5 = LoadImage(image="cat_start.png")
var_6 = VAEEncode(pixels=var_5, vae=var_1[2])
var_7 = EmptyAnimateDiffLatent(resolution=512, frame_count=16, batch_size=1)
var_8 = AnimateDiffConditioning(model=var_1, positive=var_3, negative=var_4, frame_count=16)
var_9 = KSampler(seed=987654321, steps=25, cfg=7, sampler_name="euler", scheduler="karras", denoise=1, model=var_1, positive=var_8[0], negative=var_8[1], latent_image=var_7)
var_10 = VAEDecode(samples=var_9, vae=var_1[2])
var_11 = VHS_VideoCombine(frame_rate=8, loop_count=0, filename_prefix="AnimateDiff", format="video/h264-mp4", save_output=true, images=var_10)
final_result = var_11

    """.strip()
    
    # 解析代码回DAG
    reconstructed_dag = parse_code_to_dag(generated_code)
    
    # 打印结果（格式化输出）
    print(json.dumps(reconstructed_dag, indent=2))