import yaml
import re
import json
from dag_encode import parse_code_to_dag

def parse_yaml(yaml_content):
    """解析YAML内容，提取函数参数信息"""
    return yaml.safe_load(yaml_content)

def generate_function_calls(function_list, yaml_data):
    """生成函数调用字符串"""
    var_counter = 1
    var_mapping = {}  # 跟踪每个类型的最新变量
    output_mapping = {}  # 跟踪每个函数输出的变量和类型
    
    function_calls = []
    
    # 从YAML中提取所有函数的信息
    function_info = {}
    for func_name, func_data in yaml_data.items():
        input_params = func_data.get('input_params', {})
        output_params = func_data.get('output_params', {})
        
        # 提取输出类型及其索引（按定义顺序）
        output_types = {}
        if output_params:  # 仅处理有输出参数的函数
            # 安全解析output_key，确保不抛出索引错误
            sorted_outputs = []
            for output_key in output_params:
                # 提取output_key中的数字部分（兼容各种格式）
                try:
                    # 尝试从output_key中提取数字（如output_0 -> 0）
                    key_num = int(output_key.split('_')[-1])
                except (IndexError, ValueError):
                    # 如果解析失败，使用当前长度作为索引（保底策略）
                    key_num = len(sorted_outputs)
                sorted_outputs.append((key_num, output_key))
            
            # 按数字排序并分配索引
            sorted_outputs.sort(key=lambda x: x[0])
            for index, (_, output_key) in enumerate(sorted_outputs):
                output_type = output_params[output_key]
                output_types[index] = output_type
        
        function_info[func_name] = {
            'input_params': input_params,
            'output_types': output_types,
            'output_count': len(output_params)
        }
    
    # 处理函数列表
    for func_name in function_list:
        # 如果函数不在YAML数据中，创建通用模板
        if func_name not in function_info:
            var_name = f'var_{var_counter}'
            function_calls.append(f'{var_name} = {func_name}()')
            var_counter += 1
            continue
        
        func_info = function_info[func_name]
        input_params = func_info['input_params']
        
        # 构建参数列表
        param_list = []
        for param_name, param_info in input_params.items():
            param_type = param_info.get('type', '')
            
            # 处理依赖关系
            # 将param_type转换为可哈希的字符串形式进行比较
            param_type_str = param_type if isinstance(param_type, str) else str(param_type)
            
            if param_type_str in var_mapping or (isinstance(param_type, list) and any(t in var_mapping for t in param_type)):
                # 处理枚举类型参数
                if isinstance(param_type, list):
                    # 查找第一个可用的类型
                    source_var = None
                    for t in param_type:
                        if t in var_mapping:
                            source_var = var_mapping[t]
                            break
                    # 如果都没找到，使用第一个类型
                    if source_var is None:
                        source_var = var_mapping.get(param_type[0], "")
                else:
                    source_var = var_mapping.get(param_type_str, "")
                
                # 检查是否需要索引访问
                if source_var in output_mapping:
                    # 获取该函数的所有输出类型
                    output_types = output_mapping[source_var]
                    output_count = len(output_types)
                    
                    if output_count > 1:
                        # 多输出函数，查找该类型的索引
                        # 对于枚举类型，我们需要找到匹配的类型
                        target_type = param_type if isinstance(param_type, str) else param_type[0] if param_type else ""
                        indices = [idx for idx, typ in output_types.items() if typ == target_type]
                        
                        if indices:
                            # 使用找到的第一个索引
                            index = indices[0]
                            param_value = f'{source_var}[{index}]'
                        else:
                            # 未找到特定类型的索引，使用第一个输出
                            print(f"警告: 函数 {func_name} 的参数 {param_name} 需要类型 {param_type}，但在 {source_var} 的输出中未找到此类型，使用第一个输出")
                            param_value = f'{source_var}[0]'
                    else:
                        # 单输出函数，直接使用变量名
                        param_value = source_var
                else:
                    # 不是多输出函数，直接使用变量名
                    param_value = source_var
                
                param_list.append(f'{param_name}={param_value}')
            else:
                # 使用YAML中定义的默认值（如果存在）
                if 'default' in param_info:
                    default_value = param_info['default']
                    
                    # 处理字符串类型
                    if isinstance(default_value, str):
                        # 检查是否是数字
                        if isinstance(default_value, (int, float)) or (isinstance(default_value, str) and default_value.replace('.', '', 1).isdigit()):
                            param_list.append(f'{param_name}={default_value}')
                        else:
                            param_list.append(f'{param_name}="{default_value}"')
                    else:
                        param_list.append(f'{param_name}={default_value}')
                else:
                    # 处理枚举类型参数（列表形式）
                    if isinstance(param_type, list) and len(param_type) > 0:
                        # 使用列表中的第一个选项作为默认值
                        param_list.append(f'{param_name}="{param_type[0]}"')
                    # 处理字符串表示的枚举类型
                    elif isinstance(param_type, str) and param_type.startswith('[') and param_type.endswith(']'):
                        # 提取列表中的选项
                        options = re.findall(r"['\"]([^'\"]*)['\"]", param_type)
                        if options:
                            # 使用列表中的第一个选项
                            param_list.append(f'{param_name}="{options[0]}"')
                        else:
                            # 如果列表解析失败，使用空字符串
                            param_list.append(f'{param_name}=""')
                    else:
                        # 对于其他类型，使用空字符串作为默认值
                        param_list.append(f'{param_name}=""')
        
        # 生成函数调用
        var_name = f'var_{var_counter}'
        param_str = ", ".join(param_list)
        function_call = f'{var_name} = {func_name}({param_str})'
        function_calls.append(function_call)
        
        # 记录输出信息（仅处理有输出的函数）
        output_types = func_info.get('output_types', {})
        if output_types:
            output_mapping[var_name] = output_types
            # 更新每个输出类型的最新变量
            for index, output_type in output_types.items():
                var_mapping[output_type] = var_name
        
        var_counter += 1
    
    # 添加最终结果行
    function_calls.append(f'final_result = {var_mapping.get(function_list[-1], f"var_{var_counter-1}")}')
    
    return "\n".join(function_calls)

# 示例用法
if __name__ == "__main__":
    # 指定 YAML 文件路径
    yaml_file_path = "example_merged.yaml"
    
    try:
        # 读取 YAML 文件内容
        with open(yaml_file_path, 'r', encoding='utf-8') as file:
            yaml_content = file.read()
    except FileNotFoundError:
        print(f"未找到 YAML 文件: {yaml_file_path}")
    except Exception as e:
        print(f"读取文件时出错: {e}")
    else:
        # 示例函数列表
        function_list = [
            'CheckpointLoaderSimple',
            'EmptyLatentImage', 
            'CLIPTextEncode',
            'CLIPTextEncode',
            'KSampler',
            'VAEDecode',
            'SaveImage'
        ]
        
        # 解析YAML
        yaml_data = parse_yaml(yaml_content)
        
        # 生成函数调用
        result = generate_function_calls(function_list, yaml_data).strip()
        print("生成的Python代码:")
        print(result)
        print("\n" + "="*50 + "\n")
        
        # 解析DAG
        dag = parse_code_to_dag(result)
        
        # 打印结果（格式化输出）
        print("解析后的DAG JSON结构:")
        print(json.dumps(dag, indent=2, ensure_ascii=False))