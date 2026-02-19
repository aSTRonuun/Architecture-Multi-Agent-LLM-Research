import argparse
import json

from agents import MultiAgentRAG
from ollama_client import OllamaClient
from rag import LocalRetriever


def print_result(result):
    print("\n=== PLANNER ===")
    print(json.dumps(result["plan"], ensure_ascii=False, indent=2))

    print("\n=== RETRIEVER (top chunks) ===")
    if not result["contexts"]:
        print("Nenhum contexto encontrado em docs/.")
    for i, c in enumerate(result["contexts"], 1):
        preview = c["text"].strip().replace("\n", " ")
        preview = preview[:180] + ("..." if len(preview) > 180 else "")
        print(f"{i}. {c['source']} score={c['score']:.4f} | {preview}")

    print("\n=== ANALYST (final) ===")
    print(result["final_answer"])

    print("\n=== CRITIC ===")
    print(json.dumps(result["critique"], ensure_ascii=False, indent=2))
    print(f"Rodadas de revisão: {result['revision_rounds']}")


def main():
    parser = argparse.ArgumentParser(description="Multi-agent RAG local com Ollama")
    parser.add_argument("--question", type=str, help="Pergunta do usuário")
    parser.add_argument("--model", type=str, default="llama3:8b", help="Modelo Ollama")
    parser.add_argument("--base-url", type=str, default="http://localhost:11434", help="URL Ollama")
    parser.add_argument("--docs", type=str, default="docs", help="Pasta de documentos")
    parser.add_argument("--top-k", type=int, default=4, help="Número de chunks recuperados")
    args = parser.parse_args()

    client = OllamaClient(base_url=args.base_url, model=args.model)
    retriever = LocalRetriever(docs_dir=args.docs)
    app = MultiAgentRAG(client=client, retriever=retriever, max_revision_rounds=1)

    if args.question:
        result = app.run(args.question, top_k=args.top_k)
        print_result(result)
        return

    print("Modo interativo. Digite 'sair' para encerrar.\n")
    while True:
        q = input("Pergunta> ").strip()
        if q.lower() in {"sair", "exit", "quit"}:
            break
        if not q:
            continue
        result = app.run(q, top_k=args.top_k)
        print_result(result)
        print("\n" + "-" * 80 + "\n")


if __name__ == "__main__":
    main()
