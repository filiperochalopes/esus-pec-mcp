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

const uid = () => {
  if (crypto?.randomUUID) return crypto.randomUUID()
  return `id-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

document.addEventListener('alpine:init', () => {
  Alpine.data('mcpConsole', () => ({
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
  }))
})
