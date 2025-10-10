import json
import sys
from collections import defaultdict, deque

def parse_dag_execution_order(json_file_path):
    """
    解析ComfyUI工作流JSON文件，提取按执行顺序排列的class_type列表
    
    Args:
        json_file_path: JSON文件路径
        
    Returns:
        按执行顺序排列的class_type列表
    """
    # 读取JSON文件
    with open(json_file_path, 'r', encoding='utf-8') as f:
        workflow = json.load(f)
    
    # 构建依赖图
    graph = defaultdict(list)
    in_degree = defaultdict(int)
    nodes = {}
    
    # 遍历所有节点
    for node_id, node_data in workflow.items():
        nodes[node_id] = node_data
        # 检查该节点的所有输入
        if 'inputs' in node_data:
            for input_name, input_value in node_data['inputs'].items():
                # 如果输入是引用另一个节点的输出
                if isinstance(input_value, list) and len(input_value) == 2 and isinstance(input_value[0], str):
                    source_node_id = input_value[0]
                    # 添加依赖关系: source_node_id -> node_id
                    graph[source_node_id].append(node_id)
                    in_degree[node_id] += 1
    
    # 拓扑排序
    queue = deque()
    for node_id in nodes:
        if in_degree[node_id] == 0:
            queue.append(node_id)
    
    execution_order = []
    while queue:
        current_node_id = queue.popleft()
        execution_order.append(current_node_id)
        
        for neighbor in graph[current_node_id]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    
    # 检查是否有环
    if len(execution_order) != len(nodes):
        print("警告: 工作流中可能存在循环依赖")
    
    # 将节点ID转换为class_type
    class_types = [nodes[node_id]['class_type'] for node_id in execution_order]
    
    return class_types

def main():
    # 直接指定 JSON 文件路径，需要根据实际情况修改
    json_file_paths = [
        "models_tutorial/api_bfl_flux_pro_t2i.json",
        "models_tutorial/embedding_example.json",
        "models_tutorial/gligen_textbox_example.json",
        "models_tutorial/hidream_i1_full.json",
    ]

    for json_file_path in json_file_paths:
        try:
            class_types = parse_dag_execution_order(json_file_path)
            print(class_types)

        except Exception as e:
            print(f"解析错误: {e}")

if __name__ == "__main__":
    main()