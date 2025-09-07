"""
@file tools.py
@brief Executes tool chains and model calls in workflows.
"""

import httpx
from models import MODELS
from memory import set_memory


async def execute_tool_chain(workflow_name: str, input_text: str) -> str:
    """
    Executes a workflow consisting of multiple model/tool steps.

    @param workflow_name Name of the workflow to execute
    @param input_text Initial input text for the workflow
    @return Output after executing all workflow steps
    """
    from workflows import WORKFLOWS
    steps = WORKFLOWS.get(workflow_name, [])
    output = input_text

    for step in steps:
        if step["type"] == "model":
            model = step["model"]
            action = step["action"]
            prompt = f"{action}\n\n{output}"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{MODELS[model]['endpoint']}/v1/chat/completions",
                    json={"model": model, "messages": [{"role": "user", "content": prompt}]}
                )

            output = response.json()["choices"][0]["message"]["content"]
            set_memory(f"{workflow_name}:{model}", output)

        elif step["type"] == "tool":
            # Placeholder for future tool execution
            pass

    return output