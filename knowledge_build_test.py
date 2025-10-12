import json

from main import parse_prompt_to_code

workflow_path = "./workflowbench/001.json"
print(f"加载工作流文件: {workflow_path}")
with open(workflow_path, 'r', encoding='utf-8') as f:
    workflow_json = json.load(f)
print(workflow_json,type(workflow_json))




# 转换为代码表示
print("转换为代码表示...")
try:
    workflow_code = parse_prompt_to_code(workflow_json)
except Exception as e:
    print(f"代码转换失败，使用JSON字符串作为代码表示: {e}")
    workflow_code = f"# 从JSON转换失败\n# 原始JSON: {json.dumps(workflow_json, ensure_ascii=False)[:200]}..."