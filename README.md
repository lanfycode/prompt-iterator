## 项目目标

### 总体目标

构建一个基于 LLM 的 Prompt 迭代平台，支持用户围绕 Prompt 完成从生成、测试、分析到优化的完整闭环。

### 核心闭环

$$
用户需求 \rightarrow 生成提示词 \rightarrow 生成测试用例 \rightarrow 执行测试 \rightarrow 分析结果 \rightarrow 优化提示词 \rightarrow 再测试
$$

### 启动方式
```bash
cd prompt_iterator
cp .env.example .env   # 填入 GEMINI_API_KEY
python app.py          # 默认 http://0.0.0.0:7860
```
