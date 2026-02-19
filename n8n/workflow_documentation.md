# Documentação do Workflow: AI Question Answering com Revisão

## Visão Geral

Este workflow implementa um pipeline de **resposta inteligente a perguntas** utilizando o modelo `llama3:8b` via Ollama. A pergunta do usuário passa por quatro etapas principais — planejamento, análise, crítica e (quando necessário) revisão — antes de retornar uma resposta estruturada.

**Endpoint:** `POST http://localhost:5678/webhook-test/chat`  
**Modelo LLM:** `llama3:8b` (Ollama local)  
**Status:** Inativo (modo de desenvolvimento)

---

## Fluxograma

```
[Webhook] 
    ↓ POST /chat
[Planner] — Gera um plano de resposta
    ↓
[Analyst] — Responde com base no plano
    ↓
[Critic] — Avalia a resposta (Score + APROVADO/REPROVADO)
    ↓
[IF] — Verifica status da avaliação
    ├── TRUE (APROVADO)  → [Respond to Webhook - Analyst Version]
    └── FALSE (REPROVADO) → [Revision] → [Respond to Webhook - Revision Version]
```

---

## Nodes

### 1. Webhook
**Tipo:** `n8n-nodes-base.webhook`  
**Método:** `POST`  
**Path:** `/chat`  
**Modo de resposta:** `responseNode` (aguarda o node de resposta final)

Recebe a pergunta do usuário no corpo da requisição:

```json
{
  "question": "Sua pergunta aqui"
}
```

---

### 2. Planner
**Tipo:** `HTTP Request → Ollama API`  
**URL:** `http://host.docker.internal:11434/api/generate`

Recebe a pergunta e gera um plano estratégico de como respondê-la antes de qualquer resposta direta.

**Prompt:**
```
Você é um planner estratégico. Analise a pergunta abaixo e gere um plano 
curto de como responder.

Pergunta: {$json.body.question}

Responda apenas texto.
```

**Output relevante:** `response` — texto com o plano de resposta.

---

### 3. Analyst
**Tipo:** `HTTP Request → Ollama API`  
**URL:** `http://host.docker.internal:11434/api/generate`

Utiliza o plano gerado pelo Planner para formular uma resposta aprofundada à pergunta original.

**Prompt:**
```
Você é um especialista.

Plano:
{Planner.response}

Pergunta:
{Webhook.body.question}

Resposta:
```

**Output relevante:** `response` — resposta gerada pelo modelo.

---

### 4. Critic
**Tipo:** `HTTP Request → Ollama API`  
**URL:** `http://host.docker.internal:11434/api/generate`

Avalia criticamente a resposta do Analyst, atribuindo uma nota e um status de aprovação.

**Prompt:**
```
Você é um avaliador crítico.

Pergunta: {Webhook.body.question}

Resposta gerada:
{Analyst.response}

Avalie de 0 a 10 e diga se está APROVADO ou REPROVADO.
Formato:
Score: X
Status: APROVADO ou REPROVADO
```

**Output esperado (formato obrigatório):**
```
Score: 8
Status: APROVADO
```

---

### 5. IF
**Tipo:** `n8n-nodes-base.if`

Verifica o status retornado pelo Critic usando regex para extrair o resultado da avaliação.

**Condição:**
```
$json.response.match(/Status:\s*(APROVADO|REPROVADO)/)?.[1]  equals  APROVADO
```

| Saída | Condição | Próximo node |
|-------|----------|--------------|
| **TRUE** | Status = APROVADO | Respond to Webhook (Analyst Version) |
| **FALSE** | Status = REPROVADO | Revision |

---

### 6. Revision *(executado apenas se REPROVADO)*
**Tipo:** `HTTP Request → Ollama API`  
**URL:** `http://host.docker.internal:11434/api/generate`

Recebe a resposta reprovada e gera uma versão melhorada.

**Prompt:**
```
A resposta abaixo foi reprovada.

Pergunta: {Webhook.body.question}

Resposta anterior:
{Analyst.response}

Melhore significativamente a resposta.
```

**Output relevante:** `response` — resposta revisada e melhorada.

---

### 7. Respond to Webhook — Analyst Version *(caminho APROVADO)*
**Tipo:** `n8n-nodes-base.respondToWebhook`

Retorna a resposta original do Analyst quando aprovada pelo Critic.

**Payload de resposta:**
```json
{
  "question": "pergunta original",
  "planner": "plano gerado",
  "answer": "resposta do Analyst",
  "critic": "avaliação do Critic"
}
```

---

### 8. Respond to Webhook — Revision Version *(caminho REPROVADO)*
**Tipo:** `n8n-nodes-base.respondToWebhook`

Retorna a resposta revisada pelo node Revision quando a resposta original foi reprovada.

**Payload de resposta:**
```json
{
  "question": "pergunta original",
  "planner": "plano gerado",
  "answer": "resposta do Revision (melhorada)",
  "critic": "avaliação do Critic"
}
```

---

## Exemplo de Uso

**Requisição:**
```bash
curl -X POST http://localhost:5678/webhook-test/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Explique o que são OKRs"}'
```

**Resposta (exemplo aprovado):**
```json
{
  "question": "Explique o que são OKRs",
  "planner": "1. Definir OKR...",
  "answer": "OKRs (Objectives and Key Results) são...",
  "critic": "Score: 9\nStatus: APROVADO"
}
```

---

## Infraestrutura

| Componente | Detalhe |
|------------|---------|
| **n8n** | Self-hosted v2.8.3 |
| **LLM** | Ollama (`llama3:8b`) rodando localmente |
| **Comunicação** | `host.docker.internal:11434` (n8n em Docker → Ollama no host) |
| **Protocolo** | HTTP POST com body JSON |
| **Stream** | Desativado (`stream: false`) |

---

## Notas Técnicas

- O campo `stream: false` é enviado como booleano (não string) para evitar erros de unmarshaling na API do Ollama.
- Os prompts usam `JSON.stringify()` para escapar caracteres especiais e quebras de linha automaticamente.
- O node IF usa regex `/Status:\s*(APROVADO|REPROVADO)/` com `ignoreCase: true` para maior robustez na extração do status.
- O workflow está configurado com `executionOrder: v1` e `binaryMode: separate`.
