# Instruções de Uso dos Provedores de LLM

Esta aplicação suporta múltiplos provedores de Modelos de Linguagem (LLM) através do LangChain. Você pode configurar o provedor desejado através da interface web (ícone de engrenagem) ou definindo variáveis de ambiente.

## Provedores Suportados

### 1. Anthropic (Claude)
- **Recomendado para:** Raciocínio complexo, tool calling preciso.
- **Configuração:**
  - **API Key:** Necessária. Obtenha em [console.anthropic.com](https://console.anthropic.com/).
  - **Modelo:** `claude-3-5-sonnet-20241022` (padrão), `claude-3-opus-20240229`, etc.
  - **Env Var:** `ANTHROPIC_API_KEY`

### 2. OpenAI (GPT)
- **Recomendado para:** Compatibilidade geral, velocidade (GPT-4o-mini).
- **Configuração:**
  - **API Key:** Necessária. Obtenha em [platform.openai.com](https://platform.openai.com/).
  - **Modelo:** `gpt-4o`, `gpt-4-turbo`, `gpt-3.5-turbo`.
  - **Env Var:** `OPENAI_API_KEY`

### 3. Ollama (Local)
- **Recomendado para:** Privacidade, uso offline, sem custo de API.
- **Configuração:**
  - **Instalação:** Baixe e instale o Ollama em [ollama.com](https://ollama.com/).
  - **Modelos:** Execute `ollama pull llama3` ou `ollama pull mistral`.
  - **API Base:** `http://localhost:11434` (padrão). Certifique-se de que o Ollama está rodando (`ollama serve`).
  - **Modelo na UI:** Nome do modelo baixado (ex.: `llama3`, `mistral`).
  - **API Key:** Não necessária.

### 4. Google Gemini
- **Recomendado para:** Janela de contexto grande, multimodalidade.
- **Configuração:**
  - **API Key:** Necessária. Obtenha em [aistudio.google.com](https://aistudio.google.com/).
  - **Modelo:** `gemini-1.5-pro`, `gemini-pro`.
  - **Env Var:** `GEMINI_API_KEY` (ou `GOOGLE_API_KEY`).

### 5. Mistral AI
- **Recomendado para:** Modelos open-weights eficientes.
- **Configuração:**
  - **API Key:** Necessária. Obtenha em [console.mistral.ai](https://console.mistral.ai/).
  - **Modelo:** `mistral-large-latest`, `mistral-small`, `open-mixtral-8x7b`.
  - **Env Var:** `MISTRAL_API_KEY`

### 6. MLX (Apple Silicon)
- **Recomendado para:** Execução local de alta performance em Macs com chips M1/M2/M3/M4.
- **Requisitos:**
  - MacOS com Apple Silicon.
  - Python packages: `mlx-lm`, `langchain-community`. (Já incluídos no `requirements.txt` condicionalmente ou instale manualmente).
- **Configuração:**
  - **Modelo:** ID do repositório Hugging Face (ex.: `mlx-community/Llama-3.2-3B-Instruct-4bit`).
  - **API Key:** Não necessária.
  - **Nota:** A primeira execução fará o download do modelo, o que pode levar tempo.

---

# Instruções para Modelos de Linguagem (LLM): Gemini Research

Este documento descreve as diretrizes e recomendações para o uso de Tool Calling (chamada de funções) com suporte robusto ao português em 2025, comparando modelos proprietários e de código aberto.

## Modelos Proprietários (Líderes de Mercado)

Estes modelos oferecem a maior taxa de sucesso em extrair argumentos estruturados e entender o contexto em português:

*   **Claude 3.5 Sonnet / Claude 4 (Anthropic):** Frequentemente considerado o melhor em 2025 para raciocínio lógico e precisão em tool calling. Supera o GPT-4o em tarefas complexas de codificação e extração de dados.
*   **GPT-4.5 Turbo (OpenAI):** Referência em precisão de código e suporte a plugins, com uma janela de contexto expandida para até 256k tokens. Ideal para aplicações que exigem muitas ferramentas simultâneas.
*   **Gemini 1.5 Pro / 2.5 Pro (Google):** Excelente para lidar com grandes contextos e integrações nativas com o ecossistema Google, mantendo alta performance em português.

## Modelos Open-Source (Melhor Custo-Benefício e Privacidade)

Para implementações locais ou via API de terceiros (como Groq ou Together AI):

*   **Qwen3-30B-A3B / Qwen2.5-72B-Instruct:** A série Qwen consolidou-se em 2025 como uma das melhores para tool calling e raciocínio multimodal, com resultados de benchmark superiores a muitos modelos fechados.
*   **Meta Llama 3.1 / 3.2 (8B/70B):** O modelo Llama 3.1 8B Instruct é amplamente utilizado em chatbots brasileiros devido à sua eficiência e capacidade de seguir instruções em português para chamadas de funções simples.
*   **DeepSeek-V3 / DeepSeek-R1:** Fortes competidores que combinam escala com velocidade, sendo escolhas sólidas para conteúdo multilíngue e lógica estruturada em larga escala.

## Resumo da Recomendação

| Caso de Uso | Modelo Recomendado |
| :--- | :--- |
| **Complexidade Máxima** | Claude 3.5 Sonnet ou GPT-4.5 Turbo |
| **Grande Contexto** | Gemini 1.5 Pro |
| **Custo/Open-Source** | Qwen3-30B ou Llama 3.1 70B |

> **Nota:** Ferramentas como o Hugging Face oferecem leaderboards atualizados especificamente para o desempenho de modelos em português para desenvolvedores.
