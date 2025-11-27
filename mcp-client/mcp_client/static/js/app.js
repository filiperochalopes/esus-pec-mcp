/* Alpine component para a UI MCP. */

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
    config: {
      host: '',
      port: '',
      name: '',
      user: '',
      password: '',
      ...readInitialConfig(),
    },
    tools: [],
    selectedTool: null,
    argsText: '{}',
    chat: [],
    toolCalls: [],
    logs: [],
    latestResult: null,
    busy: false,
    error: null,
    // Claude + MCP
    claudeApiKey: '',
    claudeModel: 'claude-3-5-sonnet-20241022',
    claudePrompt: '',
    claudeSystem: 'Você é um agente clínico que usa tools MCP para recuperar dados.',
    claudeMaxTurns: 4,
    claudeEvents: [],
    claudeBusy: false,
    claudeError: null,

    async init() {
      this.log('UI carregada, buscando tools...')
      await this.loadTools()
      this.statusMessage = 'Pronto para invocar tools'
      this.status = 'connected'
    },

    log(line) {
      const timestamp = new Date().toLocaleTimeString()
      this.logs.unshift(`[${timestamp}] ${line}`)
      this.logs = this.logs.slice(0, 50)
    },

    defaultArgs(tool) {
      const schema = tool?.input_schema || tool?.inputSchema || {}
      const props = schema.properties || {}
      const suggestion = {}
      Object.entries(props).forEach(([key, value]) => {
        if (value && Object.prototype.hasOwnProperty.call(value, 'default')) {
          suggestion[key] = value.default
        } else {
          suggestion[key] = ''
        }
      })
      return Object.keys(suggestion).length ? suggestion : {}
    },

    async loadTools() {
      try {
        this.busy = true
        const res = await fetch('/api/tools')
        const data = await res.json()
        this.tools = data.tools || []
        this.selectedTool = this.tools[0] || null
        this.argsText = this.selectedTool
          ? prettyJson(this.defaultArgs(this.selectedTool))
          : '{}'
        this.log(`Tools carregadas: ${this.tools.length}`)
      } catch (err) {
        this.error = 'Falha ao carregar tools'
        this.log(String(err))
      } finally {
        this.busy = false
      }
    },

    selectTool(tool) {
      this.selectedTool = tool
      this.argsText = prettyJson(this.defaultArgs(tool))
      this.latestResult = null
      this.error = null
    },

    async saveConfig() {
      this.error = null
      try {
        const res = await fetch('/api/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.config),
        })
        if (!res.ok) {
          throw new Error('Não foi possível salvar a configuração')
        }
        this.log('Configuração de banco atualizada')
        this.configOpen = false
      } catch (err) {
        this.error = err.message
        this.log(err.message)
      }
    },

    async runTool() {
      if (!this.selectedTool || this.busy) return
      this.error = null
      let parsedArgs = {}
      try {
        parsedArgs = this.argsText.trim() ? JSON.parse(this.argsText) : {}
      } catch (err) {
        this.error = 'Arguments precisam ser JSON válido.'
        return
      }

      this.busy = true
      this.status = 'connecting'
      this.statusMessage = `Rodando ${this.selectedTool.name}...`
      this.chat.unshift({
        id: uid(),
        role: 'user',
        content: `Chamar ${this.selectedTool.name}`,
        args: parsedArgs,
        ts: new Date().toISOString(),
      })

      try {
        const res = await fetch('/api/tools/call', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tool: this.selectedTool.name, arguments: parsedArgs }),
        })
        const data = await res.json()
        this.status = 'connected'
        this.statusMessage = 'Tool finalizada'

        if (!res.ok || data.ok === false) {
          const detail = data?.detail || data?.error || 'Erro ao invocar tool'
          this.error = detail
          this.log(detail)
          this.chat.unshift({
            id: uid(),
            role: 'assistant',
            content: detail,
            ts: new Date().toISOString(),
          })
          return
        }

        this.latestResult = data
        const call = {
          id: uid(),
          tool: this.selectedTool.name,
          args: data.arguments || parsedArgs,
          result: data.result,
          duration: data.duration_ms,
          ts: new Date().toISOString(),
          open: true,
        }
        this.toolCalls.unshift(call)
        this.chat.unshift({
          id: uid(),
          role: 'assistant',
          content: `Tool ${this.selectedTool.name} retornou ${Array.isArray(data.result) ? `${data.result.length} registros` : 'resultado'}.`,
          ts: new Date().toISOString(),
        })
        this.log(`Tool ${this.selectedTool.name} concluída em ${data.duration_ms}ms`)
      } catch (err) {
        this.status = 'error'
        this.statusMessage = 'Erro na execução'
        this.error = err.message
        this.log(err.message)
      } finally {
        this.busy = false
      }
    },

    formatTs(ts) {
      return new Date(ts).toLocaleTimeString()
    },

    formatJson(value) {
      return prettyJson(value)
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
      this.claudeEvents = []
      this.log('Executando Claude + MCP...')
      try {
        const res = await fetch('/api/claude/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            api_key: this.claudeApiKey,
            model: this.claudeModel,
            prompt: this.claudePrompt,
            system_prompt: this.claudeSystem,
            max_turns: this.claudeMaxTurns,
            tool_alias: 'pec',
          }),
        })
        const data = await res.json()
        if (!res.ok) {
          throw new Error(data?.detail || 'Falha ao executar o chat')
        }
        this.claudeEvents = data.events || []
        this.log(`Claude concluiu com ${this.claudeEvents.length} eventos.`)
      } catch (err) {
        this.claudeError = err.message
        this.log(err.message)
      } finally {
        this.claudeBusy = false
      }
    },
  }))
})
