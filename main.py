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
        "version": "0.11.8"
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


@app.get("/api/tags")
async def list_tags():
    """
    Returns a list of available models in Ollama format.

    @return List of available models in Ollama-compatible format
    """
    # Create response in exact same order as Ollama
    models_list = []
    
    # Process models in the same order as your original Ollama output
    model_order = [
        "ollama.com/library/yi-coder:9b",
        "ollama.com/library/deepseek-r1:latest", 
        "ollama.com/library/deepseek-coder:latest",
        "ollama.com/library/qwen3:4b-q4_K_M",
        "ollama.com/library/qwen3:8b-q4_K_M"
    ]
    
    for full_model_name in model_order:
        if full_model_name not in MODELS:
            continue
            
        model_config = MODELS[full_model_name]
        
        # Use full name to match exactly what Ollama returns
        # Match exact field order from Ollama
        model_entry = {
            "name": full_model_name,
            "model": full_model_name,
            "modified_at": model_config.get("modified_at", "2025-09-06T15:45:00.428313429+07:00"),
            "size": model_config.get("size", 2620788260),
            "digest": model_config.get("digest", "2bfd38a7daaf4b1037efe517ccb73d1a3bbd4822cf89f1a82be1569050a114e0"),
            "details": {
                "parent_model": "",
                "format": "gguf",
                "family": model_config.get("family", "qwen3"),
                "families": model_config.get("families", ["qwen3"]),
                "parameter_size": model_config.get("parameter_size", "4.0B"),
                "quantization_level": model_config.get("quantization_level", "Q4_K_M")
            }
        }
        models_list.append(model_entry)
        logger.info(f"📦 Added model: {full_model_name}")

    logger.info(f"📋 Returning {len(models_list)} models to GitHub Copilot")
    
    # Log the exact response for debugging
    response = {"models": models_list}
    logger.info(f"🔍 Full /api/tags response: {response}")
    
    return response


@app.post("/api/show")
async def show_model(request: Request):
    """
    Returns detailed information about a specific model in Ollama format.

    @param request Incoming HTTP request with model name
    @return Detailed model information in Ollama-compatible format
    """
    try:
        data = await request.json()
        model_name = data.get("name", "")
        
        logger.info(f"🔍 GitHub Copilot requesting model details for: '{model_name}'")
        
        # Handle empty model name - return first available model info
        if not model_name:
            if MODELS:
                first_model_key = list(MODELS.keys())[0]
                logger.info(f"⚠️  Empty model name, using first available: '{first_model_key}'")
                model_name = first_model_key
            else:
                logger.error("❌ No models available and empty model name requested")
                return {"error": {"message": "No model specified", "type": "invalid_request"}}
        
        # Handle both full and short model names
        full_model_name = model_name
        if not model_name.startswith("ollama.com/library/"):
            # Try to find by short name (GitHub Copilot sends short names)
            for full_name in MODELS.keys():
                short_name = full_name.replace("ollama.com/library/", "")
                if model_name == short_name:
                    full_model_name = full_name
                    logger.info(f"🔄 Mapped short name '{model_name}' to full name: '{full_model_name}'")
                    break
        
        # Find the model in our registry
        model_data = MODELS.get(full_model_name)
        if not model_data:
            logger.error(f"❌ Model {model_name} not found in registry")
            return {"error": f"Model {model_name} not found"}
        
        # Simple license placeholder instead of full Apache license
        apache_license = "Apache License 2.0"

        # Simplified modelfile
        modelfile = f"# Modelfile generated by ollama\nFROM {full_model_name}\n"

        # Simple parameters and template
        parameters = "temperature 0.6"
        template = ""

        # Return the complete response with all the details GitHub Copilot expects
        response = {
            "license": apache_license,
            "modelfile": modelfile,
            "parameters": parameters,
            "template": template,
            "details": {
                "parent_model": "",
                "format": "gguf",
                "family": model_data.get("family", "qwen3"),
                "families": [model_data.get("family", "qwen3")],
                "parameter_size": model_data.get("parameter_size", "4.0B"),
                "quantization_level": model_data.get("quantization_level", "Q4_K_M")
            },
            "model_info": {
                "general.architecture": "qwen3",
                "general.basename": "Qwen3", 
                "general.file_type": 15,
                "general.parameter_count": 4022468096,
                "general.quantization_version": 2,
                "general.size_label": "4B",
                "general.type": "model",
                "qwen3.attention.head_count": 32,
                "qwen3.attention.head_count_kv": 8,
                "qwen3.attention.key_length": 128,
                "qwen3.attention.layer_norm_rms_epsilon": 0.000001,
                "qwen3.attention.value_length": 128,
                "qwen3.block_count": 36,
                "qwen3.context_length": 40960,
                "qwen3.embedding_length": 2560,
                "qwen3.feed_forward_length": 9728,
                "qwen3.rope.freq_base": 1000000,
                "tokenizer.ggml.add_bos_token": False,
                "tokenizer.ggml.bos_token_id": 151643,
                "tokenizer.ggml.eos_token_id": 151645,
                "tokenizer.ggml.merges": None,
                "tokenizer.ggml.model": "gpt2",
                "tokenizer.ggml.padding_token_id": 151643,
                "tokenizer.ggml.pre": "qwen2",
                "tokenizer.ggml.token_type": None,
                "tokenizer.ggml.tokens": None
            },
            "tensors": [
                {"name": "output_norm.weight", "type": "F32", "shape": [2560]},
                {"name": "token_embd.weight", "type": "Q6_K", "shape": [2560, 151936]},
                {"name": "blk.0.attn_k.weight", "type": "Q4_K", "shape": [2560, 1024]},
                {"name": "blk.0.attn_k_norm.weight", "type": "F32", "shape": [128]},
                {"name": "blk.0.attn_norm.weight", "type": "F32", "shape": [2560]},
                {"name": "blk.0.attn_output.weight", "type": "Q4_K", "shape": [4096, 2560]},
                {"name": "blk.0.attn_q.weight", "type": "Q4_K", "shape": [2560, 4096]},
                {"name": "blk.0.attn_q_norm.weight", "type": "F32", "shape": [128]},
                {"name": "blk.0.attn_v.weight", "type": "F16", "shape": [2560, 1024]},
                {"name": "blk.0.ffn_down.weight", "type": "Q6_K", "shape": [9728, 2560]},
                {"name": "blk.0.ffn_gate.weight", "type": "Q4_K", "shape": [2560, 9728]},
                {"name": "blk.0.ffn_norm.weight", "type": "F32", "shape": [2560]},
                {"name": "blk.0.ffn_up.weight", "type": "Q4_K", "shape": [2560, 9728]}
                # Note: Real Ollama includes hundreds more tensor entries - truncated for brevity
            ]
        }
        
        logger.info(f"✅ Returning /api/show response for: {full_model_name}")
        return response
        
    except Exception as e:
        logger.error(f"💥 Error in show_model: {e}")
        return {
            "error": {
                "message": f"Error retrieving model information: {str(e)}",
                "type": "internal_error",
            }
        }


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
