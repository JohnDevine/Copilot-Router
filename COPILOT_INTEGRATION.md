# Copilot Router Integration Guide

## Current Setup
✅ **GitHub Copilot is now using your intelligent router**
- All chat requests go through localhost:11434
- Smart routing based on keywords and file types
- Fully integrated with VS Code's Copilot Chat interface

## How to Use

### Smart Router Keywords:
- **"use q3"** → Routes to Qwen3 8B (more powerful)
- **"use coder"** → Routes to DeepSeek Coder (coding specialist)
- **"use yi"** → Routes to Yi Coder 9B (advanced coding)
- **No keywords** → Routes to Qwen3 4B (fast default)

### Model Selection in Copilot Chat:
1. Open Copilot Chat (Cmd+Shift+I)
2. Click the model dropdown
3. Choose from:
   - **Smart Router (Auto-Select)** - Uses keyword routing
   - **Qwen3 8B** - Direct access to powerful model
   - **DeepSeek Coder** - Direct coding specialist
   - **Yi Coder 9B** - Direct advanced coding

## Switching Back to Claude

### Option 1: Quick Toggle (Temporary)
```bash
# Stop router
pkill -f "uvicorn.*11434"
# Copilot will fallback to default (Claude)
```

### Option 2: Settings Toggle (Permanent)
In VS Code settings.json, comment out these lines:
```json
// "github.copilot.chat.endpoint": "http://localhost:11434/v1",
// "github.copilot.advanced.customEndpoint": "http://localhost:11434/v1",
// "github.copilot.completions.endpoint": "http://localhost:11434/v1",
```

## Advantages of Router Integration
✅ **Full Copilot integration** - Works with inline suggestions, chat, and all features
✅ **Smart model selection** - Auto-routes based on context
✅ **Performance monitoring** - All requests logged in router
✅ **Local models** - No data sent to external APIs
✅ **Custom workflows** - Access to your workflow system
✅ **Easy toggle** - Can switch back to Claude anytime

## Router Status
- Router: http://localhost:11434
- Ollama: http://localhost:11435
- Logs: Check router terminal for routing decisions

## Example Usage
```
# In Copilot Chat:
"use coder - optimize this Python function"  → DeepSeek Coder
"use q3 - explain this complex algorithm"    → Qwen3 8B
"fix this bug"                               → Qwen3 4B (default)
```
