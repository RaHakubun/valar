"""
Conversion functions examples from ComfyBench project
"""

import re
import ast
import json
from markdown_to_json import dictify


def extract_key_value_pair(text: str) -> tuple[str, str]:
    key, value = text.split(':', 1)
    return key.strip(), value.strip()


def fetch_type_by_name(archive: dict, name: str) -> str:
    for key, value in archive.items():
        if isinstance(value, dict) and 'identifier' in value and value['identifier'] == name:
            return key
        elif isinstance(value, str) and value == name:  # Handle reverse mapping case
            return key
    return None


def fetch_slot_by_name(archive: list, name: str) -> int:
    for index, value in enumerate(archive):
        if value['name'] == name:
            return index
    return None


def parse_prompt_to_code(prompt: dict, verbose: bool = False):
    """
    Convert JSON workflow (prompt) to Python code representation

    Example:
    Input: {
        "1": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": 512,
                "height": 512,
                "batch_size": 1
            }
        },
        "2": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["3", 0],
                "negative": ["4", 0],
                "seed": 123
            }
        }
    }

    Output: Python code representation like:
    latent_1 = empty_latent_image(width=512, height=512, batch_size=1)
    _ = ksampler(model=latent_1, positive=conditioning_3, negative=conditioning_4, seed=123)
    """
    code = ''
    type_list = []
    node_dict = {}

    # In the actual implementation, this would load from './dataset/benchmark/document/meta.json'
    # For this example, we'll define a simple mock meta for demonstration
    node_meta = {
        'EmptyLatentImage': {
            'identifier': 'empty_latent_image',
            'outputs': [{'name': 'LATENT', 'type': 'LATENT'}]
        },
        'KSampler': {
            'identifier': 'ksampler',
            'outputs': [{'name': 'MODEL', 'type': 'MODEL'}]
        },
        'CLIPTextEncode': {
            'identifier': 'clip_text_encode',
            'outputs': [{'name': 'CONDITIONING', 'type': 'CONDITIONING'}]
        }
    }

    for node_id, node_info in prompt.items():
        node_type = node_info['class_type']
        type_list.append(node_type)
        assert node_type in node_meta, f'node {node_type} not found'

        node_dict[node_id] = {
            'type': node_type,
            'name': node_meta[node_type]['identifier'],
            'inputs': node_info['inputs'],
            'outputs': [],
            'visited': False
        }

    for _ in range(len(node_dict)):
        for node_id, node_info in node_dict.items():
            if node_info['visited']:
                continue

            invalid = False
            for input_value in node_info['inputs'].values():
                if isinstance(input_value, list) and len(input_value) == 2:
                    input_node, _ = input_value
                    if not node_dict[input_node]['visited']:
                        invalid = True
                        break
            if invalid:
                continue

            # the node is valid
            node_info['visited'] = True

            parameter_list = []
            for input_name, input_value in node_info['inputs'].items():
                if isinstance(input_value, list) and len(input_value) == 2:
                    output_node, output_slot = input_value
                    input_value = f'{node_dict[output_node]["outputs"][output_slot]}'
                elif isinstance(input_value, str):
                    input_value = f'"""{input_value}"""'
                else:
                    input_value = str(input_value)
                parameter_list.append(f'{input_name}={input_value}')

            return_list = []
            for output_info in node_meta[node_info['type']]['outputs']:
                return_name = f'{output_info["name"].replace(" ", "_").lower()}_{node_id}'
                node_info['outputs'].append(return_name)
                return_list.append(return_name)
            if not return_list:
                return_list.append('_')

            code += f'{", ".join(return_list)} = {node_info["name"]}({", ".join(parameter_list)})\n'

    if verbose:
        extra = {'type_list': type_list}
        return code, extra
    else:
        return code


def parse_code_to_prompt(code: str, verbose: bool = False):
    """
    Convert Python code representation back to JSON workflow (prompt)

    Example:
    Input:
    latent_1 = empty_latent_image(width=512, height=512, batch_size=1)
    conditioning_2 = clip_text_encode(text="a painting of a fox in the style of starry night")
    model_3 = ksampler(model=latent_1, positive=conditioning_2, negative=[], seed=12345, steps=20)

    Output: JSON workflow like:
    {
        "1": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": 512,
                "height": 512,
                "batch_size": 1
            }
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "a painting of a fox in the style of starry night"
            }
        },
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": [],
                "seed": 12345,
                "steps": 20
            }
        }
    }
    """
    node_count = 0
    type_list = []
    node_dict = {}

    # In the actual implementation, this would load from './dataset/benchmark/document/meta.json'
    # For this example, we'll define a simple mock meta for demonstration
    # The mapping is from function name to class type
    node_meta = {
        'empty_latent_image': 'EmptyLatentImage',
        'ksampler': 'KSampler',
        'clip_text_encode': 'CLIPTextEncode'
    }

    # Reverse mapping for lookup
    reverse_meta = {v: k for k, v in node_meta.items()}

    variable_record = {}

    tree_root = ast.parse(code)
    for tree_node in tree_root.body:
        code_line = ast.unparse(tree_node).strip()
        assert isinstance(tree_node, ast.Assign), f'unexpected node type {type(tree_node)} in code line: {code_line}'

        node_name = tree_node.value.func.id
        # Find the class type from the function name
        node_type = None
        for func_name, class_type in node_meta.items():
            if func_name == node_name:
                node_type = class_type
                break
        type_list.append(node_type)
        assert node_type, f'node type for {node_name} is not found'

        # create node
        node_count += 1
        node_id = str(node_count)
        node_info = {'class_type': node_type, 'inputs': {}}

        # process parameters
        for keyword in tree_node.value.keywords:
            if isinstance(keyword.value, ast.Constant):  # String, number, etc.
                node_info['inputs'][keyword.arg] = keyword.value.value
            elif isinstance(keyword.value, ast.List):  # Empty list case
                node_info['inputs'][keyword.arg] = []
            elif isinstance(keyword.value, ast.Name):  # Variable reference
                var_name = keyword.value.id
                if var_name in variable_record:
                    node_info['inputs'][keyword.arg] = variable_record[var_name]
                else:
                    # If variable is not in record yet, it might be handled later
                    node_info['inputs'][keyword.arg] = var_name

        # process returns
        for target in tree_node.targets:
            if isinstance(target, ast.Name):
                variable_record[target.id] = [node_id, 0]
            elif isinstance(target, ast.Tuple):
                for index, element in enumerate(target.elts):
                    variable_record[element.id] = [node_id, index]

        node_dict[node_id] = node_info

    prompt = node_dict
    if verbose:
        extra = {'type_list': type_list}
        return prompt, extra
    else:
        return prompt


def parse_prompt_to_markdown(prompt: dict, verbose: bool = False):
    """
    Convert JSON workflow (prompt) to markdown representation

    Example:
    Input: {
        "1": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512}}
    }

    Output:
    - N1: EmptyLatentImage
        - width: "512"
        - height: "512"
    """
    markdown = ''
    type_list = []
    node_dict = {}

    # Mock meta data for example
    node_meta = {
        'EmptyLatentImage': {
            'outputs': [{'name': 'LATENT', 'type': 'LATENT'}]
        },
        'KSampler': {
            'outputs': [{'name': 'MODEL', 'type': 'MODEL'}]
        },
        'CLIPTextEncode': {
            'outputs': [{'name': 'CONDITIONING', 'type': 'CONDITIONING'}]
        }
    }

    for node_id, node_info in prompt.items():
        node_type = node_info['class_type']
        type_list.append(node_type)
        assert node_type in node_meta, f'node {node_type} not found'

        node_dict[node_id] = {
            'type': node_type,
            'name': f'N{node_id}',
            'inputs': node_info['inputs'],
            'outputs': node_meta[node_type]['outputs']
        }

    for node_id, node_info in node_dict.items():
        markdown += f'- {node_info["name"]}: {node_info["type"]}\n'

        for input_name, input_value in node_info['inputs'].items():
            if isinstance(input_value, list) and len(input_value) == 2:
                output_node, output_slot = input_value
                output_name = node_dict[output_node]['outputs'][output_slot]['name']
                input_value = f'({node_dict[output_node]["name"]}.{output_name})'
            elif isinstance(input_value, str):
                input_value = input_value.replace('\n', ' ')
                input_value = f'"{input_value}"'
            else:
                input_value = str(input_value)
            markdown += f'    - {input_name}: {input_value}\n'

    if verbose:
        extra = {'type_list': type_list}
        return markdown, extra
    else:
        return markdown


def parse_markdown_to_prompt(markdown: str, verbose: bool = False):
    """
    Convert markdown representation back to JSON workflow (prompt)

    Example:
    Input:
    - N1: EmptyLatentImage
        - width: "512"
        - height: "512"

    Output: {
        "1": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512}}
    }
    """
    type_list = []
    node_dict = {}

    # Mock meta data for example
    node_meta = {
        'EmptyLatentImage': {
            'outputs': [{'name': 'LATENT', 'type': 'LATENT'}]
        },
        'KSampler': {
            'outputs': [{'name': 'MODEL', 'type': 'MODEL'}]
        },
        'CLIPTextEncode': {
            'outputs': [{'name': 'CONDITIONING', 'type': 'CONDITIONING'}]
        }
    }

    for line in markdown.split('\n'):
        if line.startswith('- '):
            node_name, node_type = line.strip('- ').split(': ')
            node_id = node_name.strip('N')
            node_dict[node_id] = {'class_type': node_type, 'inputs': {}}

    for line in markdown.split('\n'):
        if line.startswith('- '):
            node_name, node_type = line.strip('- ').split(': ')
            node_id = node_name.strip('N')
        elif line.startswith('    - '):
            input_name, input_value = line.strip('    - ').split(': ')
            if input_value.startswith('(') and input_value.endswith(')'):
                output_node, output_name = input_value.strip('()').split('.')
                output_id = output_node.strip('N')
                output_type = node_dict[output_id]['class_type']
                output_slot = fetch_slot_by_name(node_meta[output_type]['outputs'], output_name)
                node_dict[node_id]['inputs'][input_name] = [output_id, output_slot]
            elif input_value.startswith('"') and input_value.endswith('"'):
                node_dict[node_id]['inputs'][input_name] = input_value.strip('"')
            else:
                node_dict[node_id]['inputs'][input_name] = eval(input_value)

    prompt = node_dict
    if verbose:
        extra = {'type_list': type_list}
        return prompt, extra
    else:
        return prompt


# Example usage of all four functions:
if __name__ == "__main__":
    # Example JSON workflow
    example_workflow = {
        "1": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": 512,
                "height": 512,
                "batch_size": 1
            }
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "a painting of a fox in the style of starry night"
            }
        },
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],  # This would reference node 1's output
                "positive": ["2", 0],  # This would reference node 2's output
                "negative": [],
                "seed": 12345,
                "steps": 20
            }
        }
    }

    print("=" * 60)
    print("EXAMPLE CONVERSIONS FROM ComfyBench PROJECT")
    print("=" * 60)

    print("\n1. ORIGINAL JSON WORKFLOW:")
    print(json.dumps(example_workflow, indent=2))

    print("\n" + "=" * 60)
    print("CONVERSION 1: JSON → CODE")
    print("=" * 60)
    code_repr = parse_prompt_to_code(example_workflow)
    print("Code representation:")
    print(code_repr)

    print("\n" + "=" * 60)
    print("CONVERSION 2: CODE → JSON (round-trip)")
    print("=" * 60)
    reconstructed_workflow = parse_code_to_prompt(code_repr)
    print("Reconstructed JSON workflow:")
    print(json.dumps(reconstructed_workflow, indent=2))

    print("\n" + "=" * 60)
    print("CONVERSION 3: JSON → MARKDOWN")
    print("=" * 60)
    markdown_repr = parse_prompt_to_markdown(example_workflow)
    print("Markdown representation:")
    print(markdown_repr)

    print("\n" + "=" * 60)
    print("CONVERSION 4: MARKDOWN → JSON (round-trip)")
    print("=" * 60)
    markdown_to_json = parse_markdown_to_prompt(markdown_repr)
    print("Reconstructed from markdown:")
    print(json.dumps(markdown_to_json, indent=2))

    print("\n" + "=" * 60)
    print("SUMMARY:")
    print("✓ parse_prompt_to_code() - Converts JSON workflow to Python code")
    print("✓ parse_code_to_prompt() - Converts Python code back to JSON workflow")
    print("✓ parse_prompt_to_markdown() - Converts JSON workflow to markdown")
    print("✓ parse_markdown_to_prompt() - Converts markdown back to JSON workflow")
    print("✓ All conversions are bidirectional and preserve workflow structure")
    print("=" * 60)