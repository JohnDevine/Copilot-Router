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
        
        # Complete Apache License text (full version to match Ollama)
        apache_license = """                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS

   APPENDIX: How to apply the Apache License to your work.

      To apply the Apache License to your work, attach the following
      boilerplate notice, with the fields enclosed by brackets "[]"
      replaced with your own identifying information. (Don't include
      the brackets!)  The text should be enclosed in the appropriate
      comment syntax for the file format. We also recommend that a
      file or class name and description of purpose be included on the
      same "printed page" as the copyright notice for easier
      identification within third-party archives.
   Copyright 2024 Alibaba Cloud
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License."""

        # Detailed modelfile
        modelfile = f"""# Modelfile generated by "ollama show"
# To build a new Modelfile based on this, replace FROM with:
# FROM {full_model_name}

FROM /Users/johndevine/.ollama/models/blobs/sha256-163553aea1b1de62de7c5eb2ef5afb756b4b3133308d9ae7e42e951d8d696ef5
TEMPLATE \"\"\"
{{{{- $lastUserIdx := -1 -}}}}
{{{{- range $idx, $msg := .Messages -}}}}
{{{{- if eq $msg.Role "user" }}}}{{{{ $lastUserIdx = $idx }}}}{{{{ end -}}}}
{{{{- end }}}}
{{{{- if or .System .Tools }}}}<|im_start|>system
{{{{ if .System }}}}
{{{{ .System }}}}
{{{{- end }}}}
{{{{- if .Tools }}}}

# Tools

You may call one or more functions to assist with the user query.
{{{{- end -}}}}
<|im_end|>
{{{{ end }}}}
{{{{- range $i, $_ := .Messages }}}}
{{{{- $last := eq (len (slice $.Messages $i)) 1 -}}}}
{{{{- if eq .Role "user" }}}}<|im_start|>user
{{{{ .Content }}}}
<|im_end|>
{{{{ else if eq .Role "assistant" }}}}<|im_start|>assistant
{{{{ if .Content }}}}{{{{ .Content }}}}
{{{{- else if .ToolCalls }}}}<tool_call>
{{{{ range .ToolCalls }}}}{{"name": "{{{{ .Function.Name }}}}", "arguments": {{{{ .Function.Arguments }}}}}}
{{{{ end }}}}</tool_call>
{{{{- end }}}}{{{{ if not $last }}}}<|im_end|>
{{{{ end }}}}
{{{{- else if eq .Role "tool" }}}}<|im_start|>user
<tool_response>
{{{{ .Content }}}}
</tool_response><|im_end|>
{{{{ end }}}}
{{{{- if and (ne .Role "assistant") $last }}}}<|im_start|>assistant
{{{{ end -}}}}
{{{{- end }}}}\"\"\"
PARAMETER repeat_penalty 1
PARAMETER stop <|im_start|>
PARAMETER stop <|im_end|>
PARAMETER temperature 0.6
PARAMETER top_k 20
PARAMETER top_p 0.95
LICENSE \"\"\"Apache License
                           Version 2.0, January 2004\"\"\"
"""

        # Parameters
        parameters = """repeat_penalty                 1
stop                           "<|im_start|>"
stop                           "<|im_end|>"
temperature                    0.6
top_k                          20
top_p                          0.95"""

        # Template
        template = """
{{- $lastUserIdx := -1 -}}
{{- range $idx, $msg := .Messages -}}
{{- if eq $msg.Role "user" }}{{ $lastUserIdx = $idx }}{{ end -}}
{{- end }}
{{- if or .System .Tools }}<|im_start|>system
{{ if .System }}
{{ .System }}
{{- end }}
{{- if .Tools }}

# Tools

You may call one or more functions to assist with the user query.
{{- end -}}
<|im_end|>
{{ end }}
{{- range $i, $_ := .Messages }}
{{- $last := eq (len (slice $.Messages $i)) 1 -}}
{{- if eq .Role "user" }}<|im_start|>user
{{ .Content }}
<|im_end|>
{{ else if eq .Role "assistant" }}<|im_start|>assistant
{{ if .Content }}{{ .Content }}
{{- else if .ToolCalls }}<tool_call>
{{ range .ToolCalls }}{"name": "{{ .Function.Name }}", "arguments": {{ .Function.Arguments }}}
{{ end }}</tool_call>
{{- end }}{{ if not $last }}<|im_end|>
{{ end }}
{{- else if eq .Role "tool" }}<|im_start|>user
<tool_response>
{{ .Content }}
</tool_response><|im_end|>
{{ end }}
{{- if and (ne .Role "assistant") $last }}<|im_start|>assistant
{{ end -}}
{{- end }}"""

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
