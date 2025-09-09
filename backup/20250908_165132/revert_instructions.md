# Revert Instructions

## To restore original configuration:

1. **Stop the router (if running on port 11434):**
   ```bash
   pkill -f "uvicorn main:app"
   ```

2. **Stop Ollama (if moved to port 11435):**
   ```bash
   pkill -f ollama
   ```

3. **Restore original models.yaml:**
   ```bash
   cp backup/20250908_165132/models.yaml.backup models.yaml
   ```

4. **Restart Ollama on default port 11434:**
   ```bash
   ollama serve
   ```

5. **Restart router on port 8000:**
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

## Original Configuration:
- Ollama: port 11434
- Router: port 8000
- Copilot bypassed router, went directly to Ollama
