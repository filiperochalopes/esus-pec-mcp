/* Alpine component para a UI MCP simplificada. */

const readInitialConfig = () => {
  const el = document.getElementById('initial-config')
  if (!el) return {}
  try {
    return JSON.parse(el.textContent || '{}')
  } catch (err) {
    console.warn('Não foi possível ler config inicial', err)
    return {}
  }
}

const readClaudeDefaults = () => {
  const el = document.getElementById('claude-defaults')
  if (!el) return {}
  try {
    return JSON.parse(el.textContent || '{}')
  } catch (err) {
    console.warn('Não foi possível ler defaults do Claude', err)
    return {}
  }
}

const prettyJson = (value) => {
  try {
    return JSON.stringify(value, null, 2)
  } catch (err) {
    return String(value)
  }
}

const renderMarkdown = (text) => {
  if (!text) return ''
  const raw = String(text)

  const escapeHtml = (value) =>
    value
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')

  if (window.marked && window.DOMPurify) {
    // Configura GFM para tabelas, quebra de linha e desativa headers ids/mangle.
    if (!window.__markedConfigured) {
      window.marked.setOptions({ gfm: true, breaks: true, headerIds: false, mangle: false })
      window.__markedConfigured = true
    }
    const html = window.marked.parse(raw)
    return window.DOMPurify.sanitize(html)
  }

  // Fallback: escapa o texto e mantém quebras de linha legíveis.
  return escapeHtml(raw).replace(/\n/g, '<br />')
}

const uid = () => {
  if (crypto?.randomUUID) return crypto.randomUUID()
  return `id-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

const createMcpConsole = () => ({
  status: 'idle',
  statusMessage: 'Aguardando conexão MCP',
  configOpen: false,
  savingConfig: false,
  configError: null,
  config: {
    host: '',
    port: '',
    name: '',
    user: '',
    password: '',
    ...readInitialConfig(),
  },
  claudeApiKey: readClaudeDefaults().api_key || '',
  claudeModel: readClaudeDefaults().model || 'claude-3-5-sonnet-20241022',
  claudePrompt: '',
  claudeSystem: 'Você é um agente clínico que usa tools MCP para recuperar dados.',
  claudeEvents: [],
  claudeBusy: false,
  claudeError: null,

  init() {
    this.status = 'connected'
    this.statusMessage = 'Chat pronto'
  },

  formatTs(ts) {
    return new Date(ts).toLocaleTimeString()
  },

  formatJson(value) {
    return prettyJson(value)
  },

  renderMarkdown(text) {
    return renderMarkdown(text)
  },

  async saveConfig() {
    this.configError = null
    this.savingConfig = true
    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(this.config),
      })
      if (!res.ok) {
        throw new Error('Não foi possível salvar a configuração')
      }
      this.statusMessage = 'Configuração aplicada'
      this.configOpen = false
    } catch (err) {
      this.configError = err.message
      this.status = 'error'
      this.statusMessage = 'Erro ao salvar configuração'
    } finally {
      this.savingConfig = false
    }
  },

  async runClaude() {
    if (this.claudeBusy) return
    this.claudeError = null
    if (!this.claudeApiKey) {
      this.claudeError = 'Informe sua Anthropic API Key.'
      return
    }
    if (!this.claudePrompt.trim()) {
      this.claudeError = 'Digite um prompt.'
      return
    }

    this.claudeBusy = true
    this.status = 'connecting'
    this.statusMessage = 'Chamando Claude...'
    this.claudeEvents = [
      {
        id: uid(),
        type: 'USER_MESSAGE',
        text: this.claudePrompt,
        timestamp: new Date().toISOString(),
      },
    ]

    try {
      const res = await fetch('/api/claude/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: this.claudeApiKey,
          model: this.claudeModel,
          prompt: this.claudePrompt,
          system_prompt: this.claudeSystem,
          max_turns: 4,
          tool_alias: 'pec',
        }),
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data?.detail || 'Falha ao executar o chat')
      }
      this.claudeEvents = data.events || []
      this.status = 'connected'
      this.statusMessage = 'Resposta recebida'
    } catch (err) {
      this.claudeError = err.message
      this.status = 'error'
      this.statusMessage = 'Erro na execução'
    } finally {
      this.claudeBusy = false
    }
  },
})

window.mcpConsole = createMcpConsole

let mcpConsoleRegistered = false
const registerMcpConsole = () => {
  if (mcpConsoleRegistered || typeof Alpine === 'undefined') return
  Alpine.data('mcpConsole', createMcpConsole)
  mcpConsoleRegistered = true
}

// Garante registro antes do start do Alpine, independente da ordem dos scripts.
document.addEventListener('alpine:init', registerMcpConsole)
window.deferLoadingAlpine = (callback) => {
  registerMcpConsole()
  callback()
}
