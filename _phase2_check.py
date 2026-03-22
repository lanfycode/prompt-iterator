#!/usr/bin/env python3
"""Quick sanity check for Phase 2 service wiring."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import ensure_data_dirs
from repositories.database import initialize_db
ensure_data_dirs()
initialize_db()

from services.prompt_service import PromptService
from services.optimization_service import OptimizationService
from services.test_case_service import TestCaseService
from services.test_run_service import TestRunService
from services.analysis_service import AnalysisService
from services.workflow_service import WorkflowService
from services.variable_service import VariableService
from services.template_service import TemplateService
print("[1/4] Services imported OK")

ps = PromptService()
os_ = OptimizationService(ps)
tcs = TestCaseService()
trs = TestRunService()
ans = AnalysisService()
ws = WorkflowService(prompt_service=ps, optimization_service=os_,
                     test_case_service=tcs, test_run_service=trs,
                     analysis_service=ans)
vs = VariableService()
ts = TemplateService()
print("[2/4] Services instantiated OK")

from ui.main import create_ui
print("[3/4] UI module imported OK")

app = create_ui(
    prompt_service=ps,
    optimization_service=os_,
    test_case_service=tcs,
    test_run_service=trs,
    analysis_service=ans,
    workflow_service=ws,
    variable_service=vs,
    template_service=ts,
)
print("[4/4] UI built OK")
print("\n✅ Phase 2 wiring verification PASSED")
