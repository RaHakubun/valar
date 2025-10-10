"""
片段-需求匹配模块
使用LLM判断片段是否能满足需求（意图满足 > 语义相似度）
"""

from typing import List, Dict, Any, Tuple, Optional
from .data_structures import WorkflowFragment, AtomicNeed
from .llm_client import LLMClient
import prompts


class FragmentMatcher:
    """片段-需求匹配器"""
    
    def __init__(
        self,
        llm_client: LLMClient,
        matching_threshold: float = 0.65,
        use_llm: bool = True
    ):
        """
        初始化片段匹配器
        
        Args:
            llm_client: LLM客户端
            matching_threshold: 匹配阈值
            use_llm: 是否使用LLM判断（否则使用简单规则）
        """
        self.llm = llm_client
        self.matching_threshold = matching_threshold
        self.use_llm = use_llm
    
    def match_fragments_to_needs(
        self,
        fragments: List[WorkflowFragment],
        atomic_needs: List[AtomicNeed]
    ) -> Dict[str, List[WorkflowFragment]]:
        """
        将片段匹配到原子需求
        
        Args:
            fragments: 片段列表
            atomic_needs: 原子需求列表
            
        Returns:
            {need_id: [matched_fragments]} 映射
        """
        mapping = {need.need_id: [] for need in atomic_needs}
        
        for need in atomic_needs:
            # 为每个需求找匹配的片段
            matched_fragments = self._find_matching_fragments(need, fragments)
            mapping[need.need_id] = matched_fragments
        
        return mapping
    
    def _find_matching_fragments(
        self,
        need: AtomicNeed,
        fragments: List[WorkflowFragment]
    ) -> List[WorkflowFragment]:
        """
        为单个需求找匹配的片段
        
        Args:
            need: 原子需求
            fragments: 候选片段
            
        Returns:
            匹配的片段列表（按置信度排序）
        """
        scored_fragments = []
        
        for fragment in fragments:
            # 判断是否匹配
            matched, confidence, reason = self._judge_match(need, fragment)
            
            if matched and confidence >= self.matching_threshold:
                # 更新片段的匹配信息
                fragment.mapped_need_id = need.need_id
                fragment.match_confidence = confidence
                
                scored_fragments.append((confidence, fragment))
        
        # 按置信度排序
        scored_fragments.sort(key=lambda x: x[0], reverse=True)
        
        return [frag for _, frag in scored_fragments]
    
    def _judge_match(
        self,
        need: AtomicNeed,
        fragment: WorkflowFragment
    ) -> Tuple[bool, float, str]:
        """
        判断片段是否匹配需求
        
        Args:
            need: 原子需求
            fragment: 工作流片段
            
        Returns:
            (是否匹配, 置信度, 理由)
        """
        if self.use_llm:
            return self._llm_judge_match(need, fragment)
        else:
            return self._rule_based_match(need, fragment)
    
    def _llm_judge_match(
        self,
        need: AtomicNeed,
        fragment: WorkflowFragment
    ) -> Tuple[bool, float, str]:
        """
        使用LLM判断匹配（核心方法）
        
        Args:
            need: 原子需求
            fragment: 工作流片段
            
        Returns:
            (是否匹配, 置信度, 理由)
        """
        # 如果片段没有描述，先生成描述
        if not fragment.description:
            fragment.description = self._generate_fragment_description(fragment)
        
        # 构建提示词
        prompt = prompts.FRAGMENT_NEED_MATCHING_PROMPT.format(
            need_description=need.description,
            need_category=need.category,
            need_modality=need.modality,
            need_constraints=need.constraints,
            code_fragment=fragment.code,
            fragment_function=fragment.description
        )
        
        # 调用LLM
        response = self.llm.chat(
            prompt=prompt,
            system_message="你是ComfyUI工作流专家，擅长判断代码片段是否能满足用户需求。",
            json_mode=True,
            temperature=0.3  # 降低温度以获得更一致的判断
        )
        
        # 解析响应
        parsed = self.llm.parse_json_response(response)
        
        if not parsed:
            print(f"LLM判断失败，回退到规则匹配")
            return self._rule_based_match(need, fragment)
        
        matched = parsed.get('matched', False)
        confidence = parsed.get('confidence', 0.0)
        reason = parsed.get('reason', '')
        
        return matched, confidence, reason
    
    def _rule_based_match(
        self,
        need: AtomicNeed,
        fragment: WorkflowFragment
    ) -> Tuple[bool, float, str]:
        """
        基于规则的简单匹配（回退方案）
        
        Args:
            need: 原子需求
            fragment: 工作流片段
            
        Returns:
            (是否匹配, 置信度, 理由)
        """
        score = 0.0
        reasons = []
        
        # 1. 类别匹配（权重60%）
        if need.category == fragment.category:
            score += 0.6
            reasons.append(f"类别匹配({need.category})")
        elif self._category_compatible(need.category, fragment.category):
            score += 0.4
            reasons.append(f"类别兼容({need.category}≈{fragment.category})")
        
        # 2. 关键词匹配（权重30%）
        keyword_score = self._keyword_match_score(need, fragment)
        score += 0.3 * keyword_score
        if keyword_score > 0:
            reasons.append(f"关键词匹配({keyword_score:.2f})")
        
        # 3. 约束匹配（权重10%）
        constraint_score = self._constraint_match_score(need, fragment)
        score += 0.1 * constraint_score
        if constraint_score > 0:
            reasons.append(f"约束匹配({constraint_score:.2f})")
        
        matched = score >= self.matching_threshold
        reason = "; ".join(reasons) if reasons else "无匹配"
        
        return matched, score, reason
    
    def _category_compatible(self, cat1: str, cat2: str) -> bool:
        """
        判断两个类别是否兼容
        
        Args:
            cat1: 类别1
            cat2: 类别2
            
        Returns:
            是否兼容
        """
        # 定义兼容关系
        compatible_pairs = [
            ('generation', 'sampling'),
            ('editing', 'image_processing'),
            ('upscaling', 'image_enhancement'),
        ]
        
        for c1, c2 in compatible_pairs:
            if (cat1 == c1 and cat2 == c2) or (cat1 == c2 and cat2 == c1):
                return True
        
        return False
    
    def _keyword_match_score(
        self,
        need: AtomicNeed,
        fragment: WorkflowFragment
    ) -> float:
        """
        计算关键词匹配得分
        
        Args:
            need: 原子需求
            fragment: 片段
            
        Returns:
            得分 0-1
        """
        # 提取需求中的关键词
        need_keywords = set(need.description.lower().split())
        
        # 提取片段中的关键词
        fragment_text = (fragment.description + " " + fragment.code).lower()
        fragment_keywords = set(fragment_text.split())
        
        # 计算交集
        if not need_keywords:
            return 0.0
        
        intersection = need_keywords & fragment_keywords
        return len(intersection) / len(need_keywords)
    
    def _constraint_match_score(
        self,
        need: AtomicNeed,
        fragment: WorkflowFragment
    ) -> float:
        """
        计算约束匹配得分
        
        Args:
            need: 原子需求
            fragment: 片段
            
        Returns:
            得分 0-1
        """
        if not need.constraints:
            return 1.0  # 无约束则默认满足
        
        matched_count = 0
        total_count = len(need.constraints)
        
        for key, value in need.constraints.items():
            # 检查片段代码中是否包含约束值
            if str(value).lower() in fragment.code.lower():
                matched_count += 1
        
        return matched_count / total_count if total_count > 0 else 1.0
    
    def _generate_fragment_description(
        self,
        fragment: WorkflowFragment
    ) -> str:
        """
        为片段生成功能描述（使用LLM）
        
        Args:
            fragment: 工作流片段
            
        Returns:
            描述文本
        """
        prompt = prompts.FRAGMENT_DESCRIPTION_PROMPT.format(
            code_fragment=fragment.code
        )
        
        response = self.llm.chat(
            prompt=prompt,
            system_message="你是ComfyUI工作流专家，擅长分析代码功能。",
            json_mode=True,
            temperature=0.3
        )
        
        parsed = self.llm.parse_json_response(response)
        
        if parsed and 'function' in parsed:
            return parsed['function']
        else:
            # 回退到简单描述
            return fragment.category.replace('_', ' ')


class FragmentCombinationChecker:
    """片段组合可行性检查器"""
    
    def __init__(self, llm_client: LLMClient, node_defs: Dict[str, Any]):
        """
        初始化组合检查器
        
        Args:
            llm_client: LLM客户端
            node_defs: 节点定义
        """
        self.llm = llm_client
        self.node_defs = node_defs
    
    def check_combination(
        self,
        fragment_a: WorkflowFragment,
        fragment_b: WorkflowFragment
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        检查两个片段是否可以组合
        
        Args:
            fragment_a: 前一个片段
            fragment_b: 后一个片段
            
        Returns:
            (是否兼容, 连接信息)
        """
        # 构建提示词
        prompt = prompts.FRAGMENT_COMBINATION_PROMPT.format(
            fragment_a_code=fragment_a.code,
            fragment_a_outputs=fragment_a.outputs,
            fragment_b_code=fragment_b.code,
            fragment_b_inputs=fragment_b.inputs
        )
        
        # 调用LLM
        response = self.llm.chat(
            prompt=prompt,
            system_message="你是ComfyUI工作流专家，擅长分析代码片段的连接关系。",
            json_mode=True,
            temperature=0.3
        )
        
        # 解析响应
        parsed = self.llm.parse_json_response(response)
        
        if not parsed:
            # 回退到基于类型的简单检查
            return self._simple_type_check(fragment_a, fragment_b)
        
        compatible = parsed.get('compatible', False)
        return compatible, parsed
    
    def _simple_type_check(
        self,
        fragment_a: WorkflowFragment,
        fragment_b: WorkflowFragment
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        简单的类型检查（回退方案）
        
        Args:
            fragment_a: 前一个片段
            fragment_b: 后一个片段
            
        Returns:
            (是否兼容, 连接信息)
        """
        # 检查A的输出是否能满足B的输入
        a_outputs = set(fragment_a.outputs.values())
        b_inputs = set(fragment_b.inputs.values())
        
        # 找到匹配的类型
        matching_types = a_outputs & b_inputs
        
        if matching_types:
            return True, {
                "compatible": True,
                "matching_types": list(matching_types),
                "reason": "输出输入类型匹配"
            }
        else:
            return False, {
                "compatible": False,
                "reason": f"类型不匹配：A输出{a_outputs}，B需要{b_inputs}"
            }
