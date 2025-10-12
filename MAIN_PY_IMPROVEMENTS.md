# main.py 重大改进说明

## 问题背景

原始的 `main.py` 存在严重的设计缺陷：
1. **硬编码的节点元数据** - 只支持3个demo节点类型（EmptyLatentImage, KSampler, CLIPTextEncode）
2. **assert拒绝新节点** - 遇到未知节点类型直接抛出异常，阻止知识库构建
3. **无法扩展** - 无法处理任意ComfyUI工作流JSON文件

## 解决方案

### 1. 动态节点元数据管理系统

创建了 `NodeMetaManager` 类，实现：
- ✅ **动态学习** - 遇到新节点自动推断其属性
- ✅ **持久化存储** - 学到的知识保存到 `./data/node_meta.json`
- ✅ **未知节点收集** - 所有未见过的节点记录到 `./data/unknown_nodes.json`

### 2. 智能节点类型推断

基于节点名称模式自动推断输出类型：

```python
# 推断规则举例：
CheckpointLoaderSimple → outputs: [MODEL, CLIP, VAE]
CLIPTextEncode → outputs: [CONDITIONING]
KSampler → outputs: [LATENT]
VAEDecode → outputs: [IMAGE]
LoadImage → outputs: [IMAGE]
```

### 3. 移除所有硬编码和Assert

- ❌ 移除：`assert node_type in node_meta, f'node {node_type} not found'`
- ✅ 替换为：自动创建元数据，继续处理

### 4. CamelCase到snake_case自动转换

```python
EmptyLatentImage → empty_latent_image
CLIPTextEncode → clip_text_encode
KSamplerAdvanced → k_sampler_advanced
SVD_img2vid_Conditioning → svd_img2vid__conditioning
```

## 使用方法

### 测试模式
```bash
python main.py --test
```

### 处理单个工作流
```bash
python main.py workflowbench/001.json
# 输出：
# ✓ Code representation saved to: workflowbench/001_code.py
# ✓ Unknown nodes collected in: ./data/unknown_nodes.json
```

### 批量处理构建知识库
```bash
for file in workflowbench/*.json; do
    python main.py "$file"
done
```

## 效果验证

### 测试结果
处理了5个工作流文件后，系统自动学习了20种节点类型：

```
Total node types learned: 20

1. CLIPTextEncode → clip_text_encode
2. CLIPVisionEncode → clip_vision_encode
3. CLIPVisionLoader → clip_vision_loader
4. CheckpointLoaderSimple → checkpoint_loader_simple
5. EmptyLatentImage → empty_latent_image
6. IPAdapterAdvanced → ip_adapter_advanced
7. IPAdapterModelLoader → ip_adapter_model_loader
8. ImageOnlyCheckpointLoader → image_only_checkpoint_loader
9. KSampler → k_sampler
10. KSamplerAdvanced → k_sampler_advanced
11. LoadImage → load_image
12. PreviewImage → preview_image
13. SVD_img2vid_Conditioning → svd_img2vid__conditioning
14. SaveImage → save_image
15. VAEDecode → vae_decode
16. VAELoader → vae_loader
17. VHS_VideoCombine → vhs__video_combine
18. VideoLinearCFGGuidance → video_linear_cfg_guidance
19. unCLIPCheckpointLoader → un_clip_checkpoint_loader
20. unCLIPConditioning → un_clip_conditioning
```

### 生成的代码示例

输入 `workflowbench/001.json`：
```json
{
  "4": {
    "class_type": "CheckpointLoaderSimple",
    "inputs": {
      "ckpt_name": "dreamshaper_8.safetensors"
    }
  },
  ...
}
```

输出 `workflowbench/001_code.py`：
```python
model_4, clip_4, vae_4 = checkpoint_loader_simple(ckpt_name="""dreamshaper_8.safetensors""")
image_5 = empty_latent_image(batch_size=1, height=512, width=512)
conditioning_6 = clip_text_encode(clip=clip_4, text="""a photo of a cat wearing a spacesuit inside a spaceship

high resolution, detailed, 4k""")
conditioning_7 = clip_text_encode(clip=clip_4, text="""blurry, illustration""")
latent_3 = k_sampler(cfg=7, denoise=1, latent_image=image_5, model=model_4, negative=conditioning_7, positive=conditioning_6, sampler_name="""dpmpp_2m""", scheduler="""karras""", seed=636250194499614, steps=20)
image_8 = vae_decode(samples=latent_3, vae=vae_4)
_ = save_image(filename_prefix="""ComfyUI""", images=image_8)
```

## 知识库文件

### node_meta.json
存储所有学到的节点元数据：
```json
{
  "CheckpointLoaderSimple": {
    "identifier": "checkpoint_loader_simple",
    "outputs": [
      {"name": "MODEL", "type": "MODEL"},
      {"name": "CLIP", "type": "CLIP"},
      {"name": "VAE", "type": "VAE"}
    ],
    "class_type": "CheckpointLoaderSimple",
    "auto_generated": true
  }
}
```

### unknown_nodes.json
收集所有发现的未知节点（用于后续人工校验）：
```json
{
  "CheckpointLoaderSimple": {
    "identifier": "checkpoint_loader_simple",
    "outputs": [...],
    "first_seen": null,
    "occurrences": 5
  }
}
```

## 核心优势

1. ✅ **无需预标注** - 系统自动学习节点类型
2. ✅ **处理任意工作流** - 不再拒绝未知节点
3. ✅ **持续学习** - 处理的工作流越多，知识库越完善
4. ✅ **知识积累** - 自动构建节点类型知识库
5. ✅ **双向转换** - JSON ↔ Code ↔ Markdown 完全支持
6. ✅ **智能推断** - 基于命名模式推断节点属性

## 与其他模块的集成

这个改进使得整个系统能够：
- 从任意第三方工作流学习
- 构建完整的ComfyUI节点知识库
- 支持 `recorder.py` 添加任意工作流到库中
- 支持 `driver.py` 生成使用任意节点的工作流

## 下一步

现在可以：
1. 批量处理所有workflowbench文件构建知识库
2. 使用recorder.py添加社区工作流
3. 人工校验和优化unknown_nodes.json中的推断结果
4. 将学到的知识用于工作流生成系统

## 总结

这个改进从根本上解决了知识库构建的瓶颈问题，系统现在可以：
- ✅ 处理任意ComfyUI工作流JSON
- ✅ 自动学习和积累节点知识
- ✅ 持续扩展知识库
- ✅ 无需人工标注即可工作

**核心哲学变化**：从"拒绝未知"到"学习未知"。
