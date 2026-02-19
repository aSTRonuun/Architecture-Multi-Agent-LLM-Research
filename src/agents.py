import json
from typing import Dict, Any, List

from ollama_client import OllamaClient
from rag import LocalRetriever


class MultiAgentRAG:
    def __init__(
        self,
        client: OllamaClient,
        retriever: LocalRetriever,
        max_revision_rounds: int = 1,
    ):
        self.client = client
        self.retriever = retriever
        self.max_revision_rounds = max_revision_rounds

    def _safe_json(self, raw: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
        raw = raw.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(raw[start : end + 1])
                except json.JSONDecodeError:
                    return fallback
            return fallback

    def planner(self, question: str) -> Dict[str, Any]:
        prompt = f"""
Você é o agente PLANNER em um sistema RAG multi-agente.
Sua tarefa é analisar a pergunta e retornar JSON válido com este formato:
{{
  "intent": "<intenção principal>",
  "subtasks": ["<subtarefa1>", "<subtarefa2>"],
  "answer_style": "<direto|detalhado|executivo>",
  "needs_context": true
}}
Regras:
- Retorne SOMENTE JSON.
- Seja objetivo.

Pergunta do usuário:
{question}
""".strip()
        raw = self.client.generate(prompt, temperature=0.1)
        return self._safe_json(
            raw,
            {
                "intent": "responder pergunta com base em contexto",
                "subtasks": ["buscar contexto", "responder"],
                "answer_style": "detalhado",
                "needs_context": True,
            },
        )

    def analyst(self, question: str, plan: Dict[str, Any], contexts: List[Dict[str, Any]]) -> str:
        formatted_context = "\n\n".join(
            [f"[Fonte: {c['source']} | score={c['score']:.4f}]\n{c['text']}" for c in contexts]
        )
        prompt = f"""
Você é o agente ANALYST.
Use o plano e os trechos de contexto para responder a pergunta.
Se faltar informação no contexto, deixe explícito.
No final, inclua uma seção curta chamada "Fontes usadas" com os nomes dos arquivos.

Pergunta:
{question}

Plano:
{json.dumps(plan, ensure_ascii=False, indent=2)}

Contexto recuperado:
{formatted_context if formatted_context else "(sem contexto recuperado)"}
""".strip()
        return self.client.generate(prompt, temperature=0.2)

    def critic(self, question: str, answer: str, contexts: List[Dict[str, Any]]) -> Dict[str, Any]:
        context_summary = "\n\n".join(
            [f"[Fonte: {c['source']}] {c['text'][:280]}" for c in contexts]
        )
        prompt = f"""
Você é o agente CRITIC.
Avalie a resposta do ANALYST.
Critérios:
1) Aderência à pergunta
2) Aderência ao contexto recuperado
3) Clareza
Retorne SOMENTE JSON com:
{{
  "approved": true/false,
  "reason": "texto curto",
  "improvements": ["acao1", "acao2"]
}}

Pergunta:
{question}

Resumo do contexto:
{context_summary if context_summary else "(sem contexto)"}

Resposta do ANALYST:
{answer}
""".strip()
        raw = self.client.generate(prompt, temperature=0.0)
        return self._safe_json(
            raw,
            {"approved": True, "reason": "fallback", "improvements": []},
        )

    def revise(self, answer: str, critique: Dict[str, Any], contexts: List[Dict[str, Any]]) -> str:
        formatted_context = "\n\n".join(
            [f"[Fonte: {c['source']} | score={c['score']:.4f}]\n{c['text']}" for c in contexts]
        )
        prompt = f"""
Você é o agente ANALYST em modo de REVISÃO.
Melhore a resposta com base na crítica.
Mantenha fidelidade ao contexto.

Crítica:
{json.dumps(critique, ensure_ascii=False, indent=2)}

Contexto:
{formatted_context if formatted_context else "(sem contexto)"}

Resposta anterior:
{answer}
""".strip()
        return self.client.generate(prompt, temperature=0.15)

    def run(self, question: str, top_k: int = 4) -> Dict[str, Any]:
        plan = self.planner(question)

        retrieved = self.retriever.retrieve(question, top_k=top_k)
        contexts: List[Dict[str, Any]] = [
            {"source": chunk.source, "text": chunk.text, "score": score}
            for chunk, score in retrieved
        ]

        answer = self.analyst(question, plan, contexts)
        critique = self.critic(question, answer, contexts)

        rounds = 0
        while not critique.get("approved", True) and rounds < self.max_revision_rounds:
            answer = self.revise(answer, critique, contexts)
            critique = self.critic(question, answer, contexts)
            rounds += 1

        return {
            "plan": plan,
            "contexts": contexts,
            "final_answer": answer,
            "critique": critique,
            "revision_rounds": rounds,
        }
