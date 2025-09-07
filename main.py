"""
@file main.py
@brief FastAPI routing service for dynamic model selection and workflows.

This module handles:
- Incoming chat requests routed to AI models based on routing rules
- Multi-step workflow execution
- Benchmark logging for performance monitoring
"""

from fastapi import FastAPI, Request
import httpx
import time
import yaml
from memory import get_memory, set_memory
from benchmark import log_benchmark
from tools import execute_tool_chain

app = FastAPI()

# Load configuration files
with open("models.yaml") as f:
    MODELS = yaml.safe_load(f)["models"]

with open("routing_rules.yaml") as f:
    ROUTING = yaml.safe_load(f)["routing_rules"]

with open("workflows.yaml") as f:
    WORKFLOWS = yaml.safe_load(f)["workflows"]


def select_model(file_path: str, prompt: str) -> str:
    """
    Selects the appropriate model based on routing rules.

    @param file_path Path of the file for which a model is selected
    @param prompt User's input prompt
    @return Name of the selected model
    """
    ext = file_path.split('.')[-1].lower()
    prompt = prompt.lower()

    for rule in ROUTING:
        exts = rule["match"].get("file_extension", [])
        kws = rule["match"].get("prompt_contains", [])
        if (not exts or ext in exts) and (not kws or any(k in prompt for k in kws)):
            return rule["route_to"]

    return "qwen3:4b"


@app.post("/v1/chat/completions")
async def route_to_model(request: Request):
    """
    Routes a chat request to the appropriate AI model.

    @param request Incoming HTTP request with chat data
    @return JSON response from the selected model
    """
    data = await request.json()
    file_path = data.get("file", "unknown.txt")
    prompt = data["messages"][-1]["content"]
    model = select_model(file_path, prompt)
    model_cfg = MODELS[model]

    start = time.time()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{model_cfg['endpoint']}/v1/chat/completions",
            json={**data, "model": model}
        )
    end = time.time()

    log_benchmark(model, prompt, start, end)
    return response.json()


@app.post("/v1/workflows/{workflow_name}")
async def run_workflow(workflow_name: str, request: Request):
    """
    Executes a multi-step workflow.

    @param workflow_name Name of the workflow to execute
    @param request Incoming HTTP request with workflow data
    @return Result of the executed workflow
    """
    data = await request.json()
    input_text = data.get("input", "")
    result = await execute_tool_chain(workflow_name, input_text)
    return {"workflow": workflow_name, "result": result}