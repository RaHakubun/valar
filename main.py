"""
Conversion functions for ComfyUI workflow transformations
Supports bidirectional conversion between JSON, Code, and Markdown formats
Automatically handles unknown node types for knowledge base building
"""

import re
import ast
import json
import os
from typing import Dict, List, Tuple, Any, Optional
from pathlib import Path


# Node metadata storage - integrated with workflow_library
WORKFLOW_LIBRARY_PATH = './data/workflow_library'
NODE_META_FILE = os.path.join(WORKFLOW_LIBRARY_PATH, 'node_meta.json')


class NodeMetaManager:
    """Manage node metadata dynamically, learning from workflow JSONs"""
    
    def __init__(self):
        self.node_meta = self._load_node_meta()
        self.statistics = self._load_statistics()
    
    def _load_node_meta(self) -> Dict[str, Any]:
        """Load existing node metadata"""
        if os.path.exists(NODE_META_FILE):
            with open(NODE_META_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _load_statistics(self) -> Dict[str, Any]:
        """Load node statistics"""
        stats_file = os.path.join(WORKFLOW_LIBRARY_PATH, 'node_statistics.json')
        if os.path.exists(stats_file):
            with open(stats_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _save_node_meta(self):
        """Save node metadata to file"""
        os.makedirs(os.path.dirname(NODE_META_FILE), exist_ok=True)
        with open(NODE_META_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.node_meta, f, indent=2, ensure_ascii=False)
    
    def get_all_nodes(self) -> Dict[str, Any]:
        """Get all learned nodes"""
        return self.node_meta.copy()
    
    def get_node_info(self, node_type: str, node_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Get node info, create if not exists"""
        if node_type in self.node_meta:
            return self.node_meta[node_type]
        
        # Create default metadata for unknown node
        identifier = self._generate_identifier(node_type)
        
        # Try to infer outputs from node_data if provided
        outputs = self._infer_outputs(node_type, node_data)
        
        node_info = {
            'identifier': identifier,
            'outputs': outputs,
            'class_type': node_type,
            'auto_generated': True
        }
        
        # Add to node_meta
        self.node_meta[node_type] = node_info
        self._save_node_meta()
        
        # Update statistics
        if node_type not in self.statistics:
            self.statistics[node_type] = {
                'identifier': identifier,
                'outputs': outputs,
                'first_seen': None,
                'occurrences': 0
            }
        self.statistics[node_type]['occurrences'] += 1
        self._save_statistics()
        
        print(f"[INFO] New node type discovered: {node_type} -> {identifier}")
        return node_info
    
    def _generate_identifier(self, node_type: str) -> str:
        """Generate function-style identifier from class name"""
        # Convert CamelCase to snake_case
        # e.g., "CLIPTextEncode" -> "clip_text_encode"
        identifier = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', node_type)
        identifier = re.sub('([a-z0-9])([A-Z])', r'\1_\2', identifier).lower()
        return identifier
    
    def _infer_outputs(self, node_type: str, node_data: Optional[Dict] = None) -> List[Dict[str, str]]:
        """Infer output types from node name or data"""
        # Common patterns
        if 'Loader' in node_type or 'Load' in node_type:
            if 'Checkpoint' in node_type:
                return [
                    {'name': 'MODEL', 'type': 'MODEL'},
                    {'name': 'CLIP', 'type': 'CLIP'},
                    {'name': 'VAE', 'type': 'VAE'}
                ]
            elif 'ControlNet' in node_type:
                return [{'name': 'CONTROL_NET', 'type': 'CONTROL_NET'}]
            elif 'LoRA' in node_type or 'Lora' in node_type:
                return [
                    {'name': 'MODEL', 'type': 'MODEL'},
                    {'name': 'CLIP', 'type': 'CLIP'}
                ]
            elif 'VAE' in node_type:
                return [{'name': 'VAE', 'type': 'VAE'}]
            elif 'CLIP' in node_type:
                return [{'name': 'CLIP', 'type': 'CLIP'}]
        
        if 'Sampler' in node_type or 'Sample' in node_type:
            return [{'name': 'LATENT', 'type': 'LATENT'}]
        
        if 'Encode' in node_type:
            if 'Text' in node_type or 'CLIP' in node_type:
                return [{'name': 'CONDITIONING', 'type': 'CONDITIONING'}]
            elif 'VAE' in node_type:
                return [{'name': 'LATENT', 'type': 'LATENT'}]
        
        if 'Decode' in node_type:
            return [{'name': 'IMAGE', 'type': 'IMAGE'}]
        
        if 'Image' in node_type:
            if 'Save' in node_type or 'Preview' in node_type:
                return []  # Terminal nodes
            return [{'name': 'IMAGE', 'type': 'IMAGE'}]
        
        if 'Latent' in node_type:
            return [{'name': 'LATENT', 'type': 'LATENT'}]
        
        if 'Conditioning' in node_type or 'Condition' in node_type:
            return [{'name': 'CONDITIONING', 'type': 'CONDITIONING'}]
        
        # Default: assume single output with generic type
        return [{'name': 'OUTPUT', 'type': 'UNKNOWN'}]
    
    def get_reverse_mapping(self) -> Dict[str, str]:
        """Get identifier -> class_type mapping"""
        return {v['identifier']: k for k, v in self.node_meta.items()}


# Global instance
_node_meta_manager = None


def get_node_meta_manager() -> NodeMetaManager:
    """Get or create global NodeMetaManager instance"""
    global _node_meta_manager
    if _node_meta_manager is None:
        _node_meta_manager = NodeMetaManager()
    return _node_meta_manager


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
    Automatically handles unknown node types by inferring their properties

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
    latent_2 = ksampler(model=latent_1, positive=conditioning_3, negative=conditioning_4, seed=123)
    """
    code = ''
    type_list = []
    node_dict = {}
    
    meta_manager = get_node_meta_manager()

    for node_id, node_info in prompt.items():
        # Skip if not a valid node (e.g., metadata)
        if not isinstance(node_info, dict) or 'class_type' not in node_info:
            continue
            
        node_type = node_info['class_type']
        type_list.append(node_type)
        
        # Get or create node metadata
        node_meta_info = meta_manager.get_node_info(node_type, node_info)

        node_dict[node_id] = {
            'type': node_type,
            'name': node_meta_info['identifier'],
            'inputs': node_info.get('inputs', {}),  # Use .get() to handle missing inputs
            'outputs': [],
            'visited': False,
            'meta': node_meta_info
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
                    # Check if output_slot is valid
                    if output_node in node_dict and output_slot < len(node_dict[output_node]['outputs']):
                        input_value = f'{node_dict[output_node]["outputs"][output_slot]}'
                    else:
                        # Fallback: use generic output name
                        input_value = f'output_{output_node}_{output_slot}'
                elif isinstance(input_value, str):
                    input_value = f'"""{input_value}"""'
                else:
                    input_value = str(input_value)
                parameter_list.append(f'{input_name}={input_value}')

            return_list = []
            for output_info in node_info['meta']['outputs']:
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
    Automatically handles unknown node types

    Example:
    Input:
    latent_1 = empty_latent_image(width=512, height=512, batch_size=1)
    conditioning_2 = clip_text_encode(text="a painting of a fox in the style of starry night")
    latent_3 = ksampler(model=latent_1, positive=conditioning_2, negative=[], seed=12345, steps=20)

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
    
    meta_manager = get_node_meta_manager()
    reverse_meta = meta_manager.get_reverse_mapping()

    variable_record = {}

    tree_root = ast.parse(code)
    for tree_node in tree_root.body:
        code_line = ast.unparse(tree_node).strip()
        assert isinstance(tree_node, ast.Assign), f'unexpected node type {type(tree_node)} in code line: {code_line}'

        node_name = tree_node.value.func.id
        # Find the class type from the function name
        node_type = reverse_meta.get(node_name)
        
        if not node_type:
            # Try to reverse engineer from snake_case to CamelCase
            node_type = ''.join(word.capitalize() for word in node_name.split('_'))
            print(f"[WARN] Unknown function identifier '{node_name}', guessing class type as '{node_type}'")
            # Let meta manager handle it
            meta_manager.get_node_info(node_type)
        
        type_list.append(node_type)

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
    Automatically handles unknown node types

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
    
    meta_manager = get_node_meta_manager()

    for node_id, node_info in prompt.items():
        # Skip if not a valid node (e.g., metadata)
        if not isinstance(node_info, dict) or 'class_type' not in node_info:
            continue
            
        node_type = node_info['class_type']
        type_list.append(node_type)
        
        # Get or create node metadata
        node_meta_info = meta_manager.get_node_info(node_type, node_info)

        node_dict[node_id] = {
            'type': node_type,
            'name': f'N{node_id}',
            'inputs': node_info.get('inputs', {}),
            'outputs': node_meta_info['outputs']
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
    Automatically handles unknown node types

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
    
    meta_manager = get_node_meta_manager()

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
                node_meta_info = meta_manager.get_node_info(output_type)
                output_slot = fetch_slot_by_name(node_meta_info['outputs'], output_name)
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


def load_workflow_from_file(file_path: str) -> Dict:
    """Load workflow JSON from file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_workflow_to_file(workflow: Dict, file_path: str):
    """Save workflow JSON to file"""
    os.makedirs(os.path.dirname(file_path) or '.', exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)


def get_node_statistics() -> Dict:
    """Get summary of learned nodes"""
    meta_manager = get_node_meta_manager()
    return {
        'total_nodes': len(meta_manager.node_meta),
        'auto_generated': sum(1 for v in meta_manager.node_meta.values() if v.get('auto_generated', False)),
        'statistics': meta_manager.statistics
    }

def _save_statistics(self):
    """Save node statistics"""
    stats_file = os.path.join(WORKFLOW_LIBRARY_PATH, 'node_statistics.json')
    os.makedirs(os.path.dirname(stats_file), exist_ok=True)
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(self.statistics, f, indent=2, ensure_ascii=False)

# Add method to NodeMetaManager class
NodeMetaManager._save_statistics = _save_statistics


# Example usage of all four functions:
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        # Test with example workflow
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
                    "model": ["1", 0],
                    "positive": ["2", 0],
                    "negative": [],
                    "seed": 12345,
                    "steps": 20
                }
            }
        }

        print("=" * 80)
        print("ComfyUI Workflow Conversion System - Test Mode")
        print("Automatically handles unknown node types for knowledge base building")
        print("=" * 80)

        print("\n1. Original Workflow JSON:")
        print(json.dumps(example_workflow, indent=2))

        print("\n" + "=" * 80)
        print("Conversion 1: JSON → CODE")
        print("=" * 80)
        code_repr = parse_prompt_to_code(example_workflow)
        print("Code representation:")
        print(code_repr)

        print("\n" + "=" * 80)
        print("Conversion 2: CODE → JSON (round-trip)")
        print("=" * 80)
        reconstructed_workflow = parse_code_to_prompt(code_repr)
        print("Reconstructed workflow:")
        print(json.dumps(reconstructed_workflow, indent=2))

        print("\n" + "=" * 80)
        print("Conversion 3: JSON → MARKDOWN")
        print("=" * 80)
        markdown_repr = parse_prompt_to_markdown(example_workflow)
        print("Markdown representation:")
        print(markdown_repr)

        print("\n" + "=" * 80)
        print("Conversion 4: MARKDOWN → JSON (round-trip)")
        print("=" * 80)
        markdown_to_json = parse_markdown_to_prompt(markdown_repr)
        print("Workflow from Markdown:")
        print(json.dumps(markdown_to_json, indent=2))

        print("\n" + "=" * 80)
        print("Node Learning Summary:")
        print("=" * 80)
        summary = get_node_statistics()
        print(f"Total node types learned: {summary['total_nodes']}")
        print(f"Auto-generated: {summary['auto_generated']}")
        if summary['statistics']:
            print("\nLearned nodes:")
            for node_type, info in summary['statistics'].items():
                print(f"  - {node_type}: {info['identifier']} (seen {info['occurrences']} times)")

        print("\n" + "=" * 80)
        print("SUMMARY:")
        print("✓ parse_prompt_to_code() - Converts JSON workflow to Python code")
        print("✓ parse_code_to_prompt() - Converts Python code back to JSON workflow")
        print("✓ parse_prompt_to_markdown() - Converts JSON workflow to markdown")
        print("✓ parse_markdown_to_prompt() - Converts markdown back to JSON workflow")
        print("✓ All conversions handle unknown node types automatically")
        print("✓ Node metadata is saved in:", NODE_META_FILE)
        print("✓ Node statistics saved in:", os.path.join(WORKFLOW_LIBRARY_PATH, 'node_statistics.json'))
        print("=" * 80)
    
    elif len(sys.argv) > 1:
        # Process workflow file
        workflow_file = sys.argv[1]
        print(f"Processing workflow: {workflow_file}")
        
        workflow = load_workflow_from_file(workflow_file)
        code = parse_prompt_to_code(workflow)
        
        # Save code representation
        code_file = workflow_file.replace('.json', '_code.py')
        with open(code_file, 'w', encoding='utf-8') as f:
            f.write(code)
        
        print(f"✓ Code representation saved to: {code_file}")
        print(f"✓ Node metadata saved in: {NODE_META_FILE}")
        
        summary = get_node_statistics()
        if summary['total_nodes'] > 0:
            print(f"\n✓ {summary['total_nodes']} node types learned (including {summary['auto_generated']} auto-generated)")
            print("\nLearned node types:")
            for node_type in sorted(summary['statistics'].keys()):
                info = summary['statistics'][node_type]
                print(f"  - {node_type} ({info['occurrences']} occurrences)")
    
    else:
        print("Usage:")
        print("  python main.py --test              # Run test with example workflow")
        print("  python main.py <workflow.json>     # Process a workflow file")
        print("\nFeatures:")
        print("  ✓ Automatically handles unknown node types")
        print("  ✓ Learns node types dynamically for knowledge base building")
        print("  ✓ No hardcoded demo data - works with any ComfyUI workflow")
        print(f"  ✓ Node metadata saved to: {NODE_META_FILE}")
        print(f"  ✓ All data integrated with workflow_library at: {WORKFLOW_LIBRARY_PATH}")