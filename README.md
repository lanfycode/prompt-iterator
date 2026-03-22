
### 启动方式
```bash
cd prompt_iterator
cp .env.example .env   # 填入 GEMINI_API_KEY
python app.py          # 默认 http://0.0.0.0:7860
```

### 完整目录结构（35 个文件）

| 层次 | 文件 | 说明 |
|------|------|------|
| 配置 | config.py | 路径、环境变量统一收口 |
| 模型 | models/prompt.py | Phase 1+2 全量数据结构 |
| 工具 | utils/logger.py | 统一日志（控制台+文件） |
| LLM | llm/model_registry.py | 5 个 Gemini 模型注册表 |
| LLM | llm/client.py | 统一 google-genai 调用入口 |
| 数据库 | repositories/database.py | SQLite 初始化（含 Phase 2 表） |
| 数据库 | repositories/prompt_repository.py | Prompt CRUD |
| 存储 | storage/prompt_storage.py | Prompt 正文文件读写 |
| Agent | agents/prompt_generator_agent.py | 需求 → 结构化 Prompt |
| Agent | agents/prompt_optimizer_agent.py | Prompt 优化（支持分析上下文） |
| 服务 | services/prompt_service.py | 生成、优化、保存、查询 |
| 服务 | services/optimization_service.py | 优化+版本化封装 |
| 工作流 | workflows/prompt_generation_workflow.py | Phase 1 生成流程 |
| 工作流 | workflows/prompt_optimization_workflow.py | Phase 1 优化流程 |
| UI | ui/pages/prompt_generate_page.py | Prompt 生成页 |
| UI | ui/pages/prompt_optimize_page.py | Prompt 优化页（三栏） |
| UI | ui/pages/prompt_list_page.py | Prompt 管理页（支持跨页加载） |
| 入口 | app.py | 应用启动入口 |

### 阶段二扩展点

**所有 Phase 2 组件均已预留为有注释的 Stub**，包括：
- `TestCaseGeneratorAgent` / `ResultAnalyzerAgent` / `PromptIterationAgent`
- `TestCaseService` / `TestRunService` / `AnalysisService` / `WorkflowService`
- `TestExecutionWorkflow` / `OneClickOptimizationWorkflow`
- SQLite 中的 `test_cases` / `test_runs` / `analyses` / `iteration_rounds` 表（已在启动时建好）

`PromptOptimizerAgent.optimize()` 已预留 `analysis_context` 参数，Phase 2 直接传入分析结果即可驱动定向优化，无需修改接口。
