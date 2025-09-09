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
import logging
from memory import get_memory, set_memory
from benchmark import log_benchmark
from tools import execute_tool_chain

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("copilot-router")

app = FastAPI()

# Load configuration files
with open("models.yaml") as f:
    MODELS = yaml.safe_load(f)["models"]
    logger.info(f"Loaded {len(MODELS)} models from models.yaml")

with open("routing_rules.yaml") as f:
    ROUTING = yaml.safe_load(f)["routing_rules"]
    logger.info(f"Loaded {len(ROUTING)} routing rules from routing_rules.yaml")

with open("workflows.yaml") as f:
    WORKFLOWS = yaml.safe_load(f)["workflows"]
    logger.info(f"Loaded {len(WORKFLOWS)} workflows from workflows.yaml")


def select_model(file_path: str, prompt: str) -> str:
    """
    Selects the appropriate model based on routing rules.

    @param file_path Path of the file for which a model is selected
    @param prompt User's input prompt
    @return Name of the selected model
    """
    ext = file_path.split(".")[-1].lower()
    prompt_lower = prompt.lower()

    logger.info(
        f"🔍 Routing request: file='{file_path}' (ext: {ext}), prompt='{prompt[:50]}...'"
    )

    for i, rule in enumerate(ROUTING):
        exts = rule["match"].get("file_extension", [])
        kws = rule["match"].get("prompt_contains", [])

        ext_match = not exts or ext in exts
        kw_match = not kws or any(k in prompt_lower for k in kws)

        if ext_match and kw_match:
            selected_model = rule["route_to"]
            logger.info(f"✅ Rule {i+1} matched! Routing to: {selected_model}")
            if kws:
                matched_keywords = [k for k in kws if k in prompt_lower]
                logger.info(f"   📝 Matched keywords: {matched_keywords}")
            return selected_model

    default_model = "ollama.com/library/qwen3:4b-q4_K_M"
    logger.info(f"🔄 No rules matched, using fallback: {default_model}")
    return default_model


@app.post("/v1/chat/completions")
async def route_to_model(request: Request):
    """
    Routes a chat request to the appropriate AI model.

    @param request Incoming HTTP request with chat data
    @return JSON response from the selected model
    """
    try:
        data = await request.json()
        file_path = data.get("file", "unknown.txt")
        prompt = data["messages"][-1]["content"]
        model = select_model(file_path, prompt)
        model_cfg = MODELS[model]

        logger.info(f"🚀 Forwarding to {model} at {model_cfg['endpoint']}")

        start = time.time()
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{model_cfg['endpoint']}/v1/chat/completions",
                json={**data, "model": model},
            )
            response.raise_for_status()  # Raise exception for HTTP errors
        end = time.time()

        logger.info(f"⚡ Response received in {end-start:.2f}s")
        log_benchmark(model, prompt, start, end)
        return response.json()

    except httpx.ConnectError as e:
        logger.error(f"❌ Connection error to {model_cfg['endpoint']}: {e}")
        return {
            "error": {
                "message": f"Backend model server unavailable: {e}",
                "type": "connection_error",
            }
        }
    except httpx.TimeoutException as e:
        logger.error(f"⏰ Timeout error to {model_cfg['endpoint']}: {e}")
        return {
            "error": {
                "message": f"Backend model server timeout: {e}",
                "type": "timeout_error",
            }
        }
    except httpx.HTTPStatusError as e:
        logger.error(
            f"🚫 HTTP error {e.response.status_code} from {model_cfg['endpoint']}: {e}"
        )
        return {
            "error": {
                "message": f"Backend returned error: {e.response.status_code}",
                "type": "http_error",
            }
        }
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")
        return {
            "error": {
                "message": f"Internal server error: {str(e)}",
                "type": "internal_error",
            }
        }


@app.get("/api/version")
async def get_version():
    """
    Returns the API version information.

    @return Version information for compatibility
    """
    return {
        "version": "1.0.0",
        "api": "copilot-router",
        "compatible": "ollama",
        "build": int(time.time()),
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.

    @return Health status of the router
    """
    return {
        "status": "healthy",
        "timestamp": int(time.time()),
        "models_loaded": len(MODELS),
        "routing_rules_loaded": len(ROUTING),
        "workflows_loaded": len(WORKFLOWS),
    }


@app.get("/v1/models")
async def list_models():
    """
    Returns a list of available models.

    @return List of available models in OpenAI-compatible format
    """
    models_list = []
    for model_name, model_config in MODELS.items():
        models_list.append(
            {
                "id": model_name,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "ollama",
                "permission": [],
                "root": model_name,
                "parent": None,
                "mode": model_config.get("mode", "chat"),
            }
        )

    return {"object": "list", "data": models_list}


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
