curl -X POST "http://127.0.0.1:8000/v1/chat/completions" -H "Content-Type: application/json" -d '{"file":"test.py","messages":[{"role":"user","content":"use coder to optimize this function"}]}'

echo also run "
