import json
import urllib.request
from typing import Dict, Any


class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3:8b"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def generate(self, prompt: str, temperature: float = 0.2) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as response:
            body = response.read().decode("utf-8")
        parsed = json.loads(body)
        return parsed.get("response", "").strip()
