"""
需求分解模块
使用LLM将用户需求分解为原子需求
"""

from typing import List, Dict, Any
from .data_structures import AtomicNeed, DecomposedNeeds
from .llm_client import LLMClient
from .utils import generate_need_id
import prompts


class NeedDecomposer:
    """需求分解器"""
    
    def __init__(self, llm_client: LLMClient):
        """
        初始化需求分解器
        
        Args:
            llm_client: LLM客户端
        """
        self.llm = llm_client
    
    def decompose(self, user_request: str) -> DecomposedNeeds:
        """
        分解用户需求
        
        Args:
            user_request: 用户需求文本
            
        Returns:
            分解后的需求
        """
        # 构建提示词
        prompt = prompts.NEED_DECOMPOSITION_PROMPT.format(
            user_request=user_request
        )
        
        # 调用LLM
        response = self.llm.chat(
            prompt=prompt,
            system_message="""
            # 角色定义
你是一个能够对用户自然语言需求进行任务分解的智能系统。
你的目标是将复杂的用户意图拆解为若干可独立执行的原子需求（AtomicNeed），
并根据它们之间的逻辑关系构建依赖图（DAG），
最终输出一个严格符合 DecomposedNeeds 数据结构的 JSON 对象。

# 数据结构定义
你必须输出一个 JSON 对象，结构必须严格符合以下格式：
{
  "atomic_needs": [
    {
      "need_id": "N1",
      "description": "原子需求的自然语言描述",
      "category": "任务类型（见下表）",
      "modality": "输入->输出",
      "priority": 5,
      "dependencies": ["N前置任务ID列表，可为空"],
      "constraints": { "参数约束或说明，可为空" }
    }
  ],
  "dependency_graph": {
    "N1": [],
    "N2": ["N1"]
  },
  "execution_order": ["N1", "N2"]
}

禁止输出除 JSON 以外的任何文字或说明。

# 原子需求定义原则
1. 若用户需求简单，可直接生成一个原子需求；
2. 若用户需求复杂，应拆解为多个原子需求；
3. 每个原子需求必须是一个完整的输入→输出映射；
4. 原子需求间若存在依赖关系（即后续任务需要前一步的结果），必须显式在 `dependencies` 中声明。

# 任务类型与输入输出映射表
| 任务类型 | 输入 | 输出 |
|-----------|-------|------|
| 语音生成 | 文本 | 语音 |
| 文生图 | 文本 | 图像 |
| 图生图 | 图像 | 图像 |
| 图像编辑 | 图像 | 图像 |
| 文生视频 | 文本 | 视频 |
| 图生视频 | 图像 | 视频 |
| 视频编辑 | 视频 | 视频 |
| 3D生成 | 图像 | 三维模型 |

# 输出字段说明
- need_id: 从 N1 开始编号，依次递增；
- description: 用简洁自然语言描述该原子任务；
- category: 对应上表的任务类型；
- modality: 用 "input->output" 表达输入输出模态；
- dependencies: 若无依赖，设为 [];
- constraints: 参数限制或特定条件，如分辨率、时长、风格等；
- dependency_graph: 所有任务的依赖关系，以 JSON 字典形式表示；
- execution_order: 任务的拓扑排序顺序。

# 输出要求
- 输出必须是**严格的 JSON 格式**；
- 在整个工作步骤需要你思考，但不允许包含解释、注释、说明文字；
- 所有字段必须存在，即使为空；
- 字段名必须与定义完全一致；
- `category` 必须为上述八个之一；
- `modality` 必须符合 `"输入->输出"` 格式。

# 示例 1
用户需求：
“根据这段文案生成配音，再用配音和封面图制作视频介绍。”
思考过程：
The user's goal is to create a short video introduction using both text and an image. 
To achieve this, the process must first transform the input text into an audio narration, since the video requires a voice-over track. 
Then, the generated audio should be combined with a provided cover image to produce the final video. 
Therefore, there are two sequential atomic tasks: (1) text-to-audio generation, and (2) image-to-video synthesis using the audio from step one as input. 
The dependency between them is direct—N2 depends on the output of N1.
输出：
{"reasoning": "The user's goal is to create a short video introduction using both text and an image. 
To achieve this, the process must first transform the input text into an audio narration, since the video requires a voice-over track. 
Then, the generated audio should be combined with a provided cover image to produce the final video. 
Therefore, there are two sequential atomic tasks: (1) text-to-audio generation, and (2) image-to-video synthesis using the audio from step one as input. 
The dependency between them is direct—N2 depends on the output of N1.",
  "atomic_needs": [
    {
      "need_id": "N1",
      "description": "根据给定文案生成配音音频",
      "category": "语音生成",
      "modality": "text->audio",
      "priority": 5,
      "dependencies": [],
      "constraints": {}
    },
    {
      "need_id": "N2",
      "description": "使用封面图和配音音频生成视频介绍",
      "category": "图生视频",
      "modality": "image->video",
      "priority": 5,
      "dependencies": ["N1"],
      "constraints": { "audio_source": "来自 N1 的输出" }
    }
  ],
  "dependency_graph": {
    "N1": [],
    "N2": ["N1"]
  },
  "execution_order": ["N1", "N2"]
}

# 示例 2
输入：
You are given an image `large_castle.png`, which is a photo of a large castle. 
First follow its style to generate a new image of a large church. 
Then convert it into a 2-second video of the church. 
Finally, upscale it by 2x and interpolate it to increase the frame rate by 3x. 
The result should be a high-quality video of a church.

输出：
{
"reasoning": "The user's goal is to create a high-quality video of a church, beginning with a reference image of a castle. 
The process can be divided into four sequential stages: 
(1) perform style-based image editing, where the input castle image guides the generation of a church image in similar style; 
(2) convert that church image into a short 2-second video clip, implying an image-to-video generation step; 
(3) enhance the resulting video resolution by upscaling it 2x, a video editing operation; and 
(4) apply frame interpolation to increase smoothness and frame rate by 3x, another video editing step. 
Each operation depends on the previous one’s output, forming a strictly linear dependency chain N1 → N2 → N3 → N4.",
  "atomic_needs": [
    {
      "need_id": "N1",
      "description": "Follow the style of large_castle.png to generate a new image of a large church.",
      "category": "图像编辑",
      "modality": "image->image",
      "priority": 5,
      "dependencies": [],
      "constraints": { "reference_image": "large_castle.png" }
    },
    {
      "need_id": "N2",
      "description": "Convert the generated church image into a 2-second video.",
      "category": "图生视频",
      "modality": "image->video",
      "priority": 5,
      "dependencies": ["N1"],
      "constraints": { "duration": "2s" }
    },
    {
      "need_id": "N3",
      "description": "Upscale the generated church video by 2x.",
      "category": "视频编辑",
      "modality": "video->video",
      "priority": 5,
      "dependencies": ["N2"],
      "constraints": { "scale_factor": "2x" }
    },
    {
      "need_id": "N4",
      "description": "Interpolate the upscaled video to increase the frame rate by 3x.",
      "category": "视频编辑",
      "modality": "video->video",
      "priority": 5,
      "dependencies": ["N3"],
      "constraints": { "frame_rate_multiplier": "3x" }
    }
  ],
  "dependency_graph": {
    "N1": [],
    "N2": ["N1"],
    "N3": ["N2"],
    "N4": ["N3"]
  },
  "execution_order": ["N1", "N2", "N3", "N4"]
}

# 示例 3
输入：
First generate an image of a woman riding a motorcycle on a highway. 
Then replace the background with a modern city skyline at night. 
The result should be a high-quality image of a motorcycle rider with a city skyline background.

输出：
{"reasoning": "The user's intent is to create a final high-quality image of a woman riding a motorcycle with a modern city skyline background. 
To accomplish this, the process naturally divides into two dependent steps: 
(1) generate the base image from text—a woman riding a motorcycle on a highway—using text-to-image generation; 
(2) modify that generated image by replacing the background with a modern city skyline at night, which constitutes an image editing operation. 
Since the second task operates directly on the output of the first, the dependency chain is linear: N1 → N2.",
  "atomic_needs": [
    {
      "need_id": "N1",
      "description": "Generate an image of a woman riding a motorcycle on a highway.",
      "category": "文生图",
      "modality": "text->image",
      "priority": 5,
      "dependencies": [],
      "constraints": {}
    },
    {
      "need_id": "N2",
      "description": "Replace the background with a modern city skyline at night.",
      "category": "图像编辑",
      "modality": "image->image",
      "priority": 5,
      "dependencies": ["N1"],
      "constraints": { "background": "modern city skyline at night" }
    }
  ],
  "dependency_graph": {
    "N1": [],
    "N2": ["N1"]
  },
  "execution_order": ["N1", "N2"]
}

# 现在请根据以上规则，对以下用户需求进行任务分解：

            """,
            json_mode=False
        )

        # 解析响应
        parsed = self.llm.parse_json_response(response)
        if not parsed or 'atomic_needs' not in parsed:
            print("需求分解失败，使用默认单一需求")
            return self._fallback_decomposition(user_request)
        
        # 构建AtomicNeed对象
        atomic_needs = []
        for need_data in parsed['atomic_needs']:
            atomic_need = AtomicNeed(
                need_id=need_data.get('need_id', generate_need_id()),
                description=need_data.get('description', ''),
                category=need_data.get('category', 'unknown'),
                modality=need_data.get('modality', 'image'),
                priority=need_data.get('priority', 5),
                dependencies=need_data.get('dependencies', []),
                constraints=need_data.get('constraints', {})
            )
            atomic_needs.append(atomic_need)
        
        # 构建依赖图
        dependency_graph = self._build_dependency_graph(atomic_needs)
        
        # 拓扑排序
        execution_order = self._topological_sort(dependency_graph)

        DecomposedReqs = DecomposedNeeds(
            atomic_needs=atomic_needs,
            dependency_graph=dependency_graph,
            execution_order=execution_order
        )
        print(DecomposedReqs)

        return DecomposedReqs
    
    def _fallback_decomposition(self, user_request: str) -> DecomposedNeeds:
        """
        回退方案：将整个需求作为单一原子需求
        
        Args:
            user_request: 用户需求
            
        Returns:
            单一需求的分解结果
        """
        need_id = generate_need_id()
        atomic_need = AtomicNeed(
            need_id=need_id,
            description=user_request,
            category='generation',
            modality='image',
            priority=10,
            dependencies=[],
            constraints={}
        )
        
        return DecomposedNeeds(
            atomic_needs=[atomic_need],
            dependency_graph={need_id: []},
            execution_order=[need_id]
        )
    
    def _build_dependency_graph(self, atomic_needs: List[AtomicNeed]) -> Dict[str, List[str]]:
        """
        构建依赖图
        
        Args:
            atomic_needs: 原子需求列表
            
        Returns:
            依赖图 {need_id: [dependent_need_ids]}
        """
        graph = {need.need_id: [] for need in atomic_needs}
        
        for need in atomic_needs:
            for dep in need.dependencies:
                if dep in graph:
                    graph[dep].append(need.need_id)
        
        return graph
    
    def _topological_sort(self, graph: Dict[str, List[str]]) -> List[str]:
        """
        拓扑排序（Kahn算法）
        
        Args:
            graph: 依赖图
            
        Returns:
            执行顺序
        """
        # 计算入度
        in_degree = {node: 0 for node in graph}
        for node in graph:
            for neighbor in graph[node]:
                in_degree[neighbor] += 1
        
        # 找到所有入度为0的节点
        queue = [node for node in graph if in_degree[node] == 0]
        result = []
        
        while queue:
            node = queue.pop(0)
            result.append(node)
            
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # 检查是否存在环
        if len(result) != len(graph):
            print("警告: 依赖图中存在环！")
            # 返回所有节点（忽略依赖关系）
            return list(graph.keys())
        
        return result
