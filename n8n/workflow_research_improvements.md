# Melhorias e Considerações para Pesquisa de Consumo Energético

## Contexto

Este documento complementa a documentação técnica do workflow e detalha melhorias, variações experimentais, questões de pesquisa e infraestrutura de medição recomendadas para um estudo comparativo de consumo energético em pipelines multi-agente com LLMs.

---

## 2. Melhorias no Workflow para a Pesquisa

### 2.1 Captura de Métricas por Node

O Ollama já retorna dados de desempenho em cada resposta que atualmente são ignorados pelo workflow. Além do campo `response`, cada chamada devolve:

```json
{
  "total_duration": 5000000000,
  "eval_count": 128,
  "prompt_eval_count": 45,
  "eval_duration": 4000000000
}
```

A melhoria consiste em adicionar um node **Set** após cada HTTP Request (Planner, Analyst, Critic e Revision) para extrair e preservar esses campos antes que o dado seja sobrescrito pelo próximo node.

| Campo Ollama | Significado | Uso na pesquisa |
|---|---|---|
| `total_duration` | Tempo total da chamada (ns) | Proxy de tempo de CPU/GPU |
| `eval_count` | Tokens gerados na resposta | Custo de geração |
| `prompt_eval_count` | Tokens do prompt de entrada | Custo de prefill |
| `eval_duration` | Tempo gasto na geração (ns) | Isolamento do custo de inferência |

### 2.2 Node de Agregação Final

Antes de cada **Respond to Webhook**, adicionar um node que consolide todas as métricas coletadas em um único objeto retornado junto com a resposta:

```json
{
  "question": "...",
  "answer": "...",
  "metrics": {
    "path": "approved",
    "total_tokens": 450,
    "total_duration_ms": 12000,
    "nodes_executed": 3,
    "calls": {
      "planner":  { "tokens_in": 45,  "tokens_out": 80,  "duration_ms": 2000 },
      "analyst":  { "tokens_in": 120, "tokens_out": 200, "duration_ms": 5000 },
      "critic":   { "tokens_in": 90,  "tokens_out": 90,  "duration_ms": 2500 },
      "revision": { "tokens_in": 110, "tokens_out": 210, "duration_ms": 5500 }
    }
  }
}
```

O campo `path` (`approved` ou `revised`) permite separar automaticamente os dois grupos de execução na análise de dados.

---

## 3. Variações para o Experimento

Para uma pesquisa robusta é necessário definir **grupos de controle e comparação**. Abaixo estão as variações recomendadas, em ordem crescente de complexidade:

### Variação A — Single-Agent (Baseline)
Workflow com apenas um node LLM respondendo diretamente à pergunta, sem Planner, Critic ou Revision. Este é o **ponto zero de comparação energética** — toda análise de custo-benefício dos demais agentes parte deste número.

```
[Webhook] → [LLM Direto] → [Respond to Webhook]
```

### Variação B — Multi-Agent sem Revision
Mantém Planner, Analyst e Critic, mas o IF sempre encaminha para o Respond to Webhook independentemente da avaliação. Mede o custo fixo do pipeline multi-agente **sem o loop de revisão**.

```
[Webhook] → [Planner] → [Analyst] → [Critic] → [Respond to Webhook]
```

### Variação C — Multi-Agent sem Planner
Remove o Planner e passa a pergunta diretamente ao Analyst. Isola o custo e o benefício da etapa de planejamento.

```
[Webhook] → [Analyst] → [Critic] → [IF] → [Respond / Revision]
```

### Variação D — Critic com Threshold Numérico (atual + melhoria)
Em vez de usar o status binário APROVADO/REPROVADO, o IF passa a usar o Score numérico retornado pelo Critic. Apenas scores abaixo de um limiar (ex: `< 7`) disparam a Revision, potencialmente reduzindo revisões desnecessárias e o consumo associado.

```
IF Score < 7 → Revision
IF Score ≥ 7 → Respond to Webhook
```

### Resumo das Variações

| Variação | Nodes LLM (aprovado) | Nodes LLM (reprovado) | Objetivo |
|---|---|---|---|
| A — Baseline | 1 | 1 | Referência energética |
| B — Sem Revision | 3 | 3 | Custo fixo multi-agente |
| C — Sem Planner | 2 | 3 | Valor do planejamento |
| D — Threshold | 3 | 4 | Otimização do loop |
| **Atual** | **3** | **4** | Pipeline completo |

---

## 4. Questões de Pesquisa

As perguntas abaixo guiam a análise dos dados coletados e podem ser respondidas cruzando as métricas de tokens, duração e consumo elétrico entre as variações:

**Q1 — O loop de Revision se justifica energeticamente?**
O caminho com Revision (4 chamadas LLM) produz respostas mensuravelmente melhores em relação ao custo energético adicional em comparação ao caminho direto (3 chamadas)?

**Q2 — Qual é a taxa de aprovação do Critic?**
Se o Critic aprova 90% das execuções, seu custo energético fixo mal se justifica. A taxa de reprovação precisa ser alta o suficiente para que o loop de revisão agregue valor real ao pipeline.

**Q3 — O Planner agrega qualidade proporcional ao seu custo?**
Comparando a Variação C (sem Planner) com o pipeline atual, a etapa de planejamento melhora a qualidade da resposta final de forma que justifique o consumo energético adicional?

**Q4 — Qual é o custo energético por token em cada etapa?**
Etapas com prompts maiores (como o Analyst, que recebe o plano completo como contexto) consomem proporcionalmente mais energia por token gerado do que etapas com prompts menores?

**Q5 — Qual é o breakeven energético do pipeline multi-agente?**
A partir de qual nível de qualidade mínima exigida o pipeline multi-agente passa a ser mais eficiente energeticamente do que múltiplas chamadas ao single-agent até obter uma resposta satisfatória?

---

## 5. Infraestrutura de Medição Recomendada

A coleta de métricas deve ocorrer em duas camadas: **dentro do workflow** (dados do Ollama) e **no nível do sistema operacional** (consumo elétrico real).

### 5.1 Métricas do Ollama (nível de aplicação)

Já disponíveis em cada resposta da API, conforme descrito na seção 2.1. Não requerem instalação adicional — apenas adaptação do workflow para preservar os campos.

### 5.2 Consumo Elétrico Real (nível de sistema)

| Ferramenta | Uso | Plataforma |
|---|---|---|
| `scaphandre` | Exporta consumo por processo em tempo real, compatível com Prometheus e Grafana | Linux (CPU) |
| `nvidia-smi dmon` | Captura wattagem da GPU por segundo | NVIDIA GPU |
| `powerstat` | Monitoramento simples de consumo do sistema | Linux |
| `CodeCarbon` | Biblioteca Python que estima emissões de CO₂ por execução de código | Multiplataforma |

### 5.3 Correlação entre Camadas

Cada execução no n8n possui um `executionId` único. O fluxo recomendado de correlação é:

```
1. Iniciar coleta de energia no host (scaphandre / nvidia-smi)
2. Registrar timestamp de início da execução n8n
3. Executar o workflow — capturar executionId
4. Registrar timestamp de fim
5. Cruzar o intervalo de tempo com os dados de energia coletados externamente
6. Associar o consumo ao executionId e ao path (approved / revised)
```

### 5.4 Stack de Observabilidade Sugerida

```
n8n (métricas de tokens) + scaphandre (energia) 
    ↓
Prometheus (coleta e armazenamento)
    ↓
Grafana (visualização e dashboards)
```

Esta stack permite criar dashboards comparando consumo energético por variação de workflow, por tipo de pergunta e por caminho de execução em tempo real.

---

## Referências e Próximos Passos

- Definir o conjunto de perguntas de teste — idealmente com diferentes níveis de complexidade para verificar se o comportamento do Critic e o consumo variam com a dificuldade da tarefa
- Executar cada variação com o mesmo conjunto de perguntas para garantir comparabilidade
- Coletar no mínimo 30 execuções por variação para viabilidade estatística
- Considerar normalizar os resultados por qualidade de resposta (ex: avaliação humana ou por um LLM externo) para calcular uma métrica de **eficiência energética por unidade de qualidade**
