# Multi-Agent RAG local com Ollama (`llama3:8b`)

Este projeto mostra como sair de um fluxo RAG de agente único para um pipeline **multi-agente sequencial**:

1. `Planner` -> entende a pergunta e cria um plano.
2. `Retriever` -> busca contexto em `docs/`.
3. `Analyst` -> responde usando plano + contexto.
4. `Critic` -> avalia e aprova (ou pede revisão).

Tudo roda localmente, usando seu Ollama.

## Requisitos

- Python 3.10+
- Ollama em execução
- Modelo `llama3:8b` disponível

Verificação rápida:

```bash
ollama list
curl http://localhost:11434/api/tags
```

## Estrutura

- `src/ollama_client.py`: cliente HTTP para Ollama
- `src/rag.py`: retriever local (TF-IDF simples sem dependências)
- `src/agents.py`: agentes e orquestração sequencial
- `src/main.py`: CLI para executar e visualizar as etapas
- `docs/conhecimento.md`: base de conhecimento de exemplo

## Como executar

```bash
cd /Users/vitoralves/Documents/New\ project
python3 src/main.py --model llama3:8b --docs docs
```

Modo pergunta única:

```bash
python3 src/main.py --model llama3:8b --question "Como devo estruturar OKRs para um time novo?"
```

## O que você verá

No terminal, para cada pergunta:

- Saída do `Planner` (JSON)
- Chunks recuperados no `Retriever` (TO-DO)
- Resposta final do `Analyst`
- Avaliação do `Critic`

Isso te dá transparência para evoluir sua arquitetura de agentes.

---

## Como replicar no n8n (sequencial)

Você pode mapear o pipeline acima para nós do n8n assim:

1. `Webhook` (entrada)
2. `AI Agent - Planner`
3. `Code` (parse JSON do planner) (To-do)
4. `AI Agent - Retriever` (ou node de busca em vector store) (To-do)
5. `AI Agent - Analyst`
6. `AI Agent - Critic`
7. `IF` (`approved == true?`)
8. `AI Agent - Analyst (revision)` (se `false`)
9. `Respond to Webhook`

### Prompt base do Planner

```text
Você é o agente PLANNER em um sistema RAG multi-agente.
Retorne SOMENTE JSON com:
{
  "intent": "...",
  "subtasks": ["..."],
  "answer_style": "direto|detalhado|executivo",
  "needs_context": true
}
Pergunta: {{$json.question}}
```

### Prompt base do Critic

```text
Você é o agente CRITIC.
Avalie se a resposta do analyst está aderente ao contexto recuperado.
Retorne SOMENTE JSON:
{
  "approved": true/false,
  "reason": "...",
  "improvements": ["..."]
}
Pergunta: {{$json.question}}
Contexto: {{$json.context}}
Resposta: {{$json.answer}}
```

## Integração n8n + Ollama local

No n8n, configure o modelo para chamar o endpoint local do Ollama:

- Base URL: `http://host.docker.internal:11434` (n8n em Docker no Mac/Windows)
- Base URL: `http://localhost:11434` (n8n fora de Docker)
- Model: `llama3:8b`

Se quiser embeddings locais depois, adicione um modelo de embedding no Ollama e troque o retriever para vector store no n8n.

Guia detalhado nó a nó:

- `/Users/vitoralves/Documents/New project/n8n/N8N_SETUP.md`

---

## Próximos passos práticos

1. Rodar o exemplo local e validar a sequência dos agentes.
2. Migrar o mesmo desenho para n8n com os prompts acima.
3. Trocar o retriever TF-IDF por vector store quando quiser aumentar precisão semântica.
