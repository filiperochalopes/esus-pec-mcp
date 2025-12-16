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

const linkifyPatientMentions = (html) => {
  if (!html) return ''
  const wrapper = document.createElement('div')
  wrapper.innerHTML = html
  const regex = /@([0-9]{1,10})/g

  const nodes = []
  const walker = document.createTreeWalker(wrapper, NodeFilter.SHOW_TEXT)
  while (walker.nextNode()) {
    nodes.push(walker.currentNode)
  }

  nodes.forEach((textNode) => {
    const parent = textNode.parentElement
    if (!parent || parent.closest('code, pre')) return
    const text = textNode.textContent
    regex.lastIndex = 0
    let match
    let lastIndex = 0
    const frag = document.createDocumentFragment()

    while ((match = regex.exec(text))) {
      const before = text.slice(lastIndex, match.index)
      if (before) frag.appendChild(document.createTextNode(before))
      const patientId = match[1]
      const tag = document.createElement('span')
      tag.className = 'patient-mention'
      tag.dataset.patientId = patientId
      tag.textContent = `@${patientId}`
      tag.setAttribute('role', 'link')
      tag.setAttribute('tabindex', '0')
      frag.appendChild(tag)
      lastIndex = match.index + match[0].length
    }

    const rest = text.slice(lastIndex)
    if (rest) frag.appendChild(document.createTextNode(rest))
    if (frag.childNodes.length) {
      parent.replaceChild(frag, textNode)
    }
  })

  return wrapper.innerHTML
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
    const html = linkifyPatientMentions(window.marked.parse(raw))
    return window.DOMPurify.sanitize(html)
  }

  // Fallback: escapa o texto e mantém quebras de linha legíveis.
  return linkifyPatientMentions(escapeHtml(raw).replace(/\n/g, '<br />'))
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
  claudeSystem:
    'Você é um agente clínico que usa tools MCP para recuperar dados. Sempre que responder com pacientes (lista ou item), acrescente o identificador real no formato @<paciente_id> usando o co_seq_cidadao devolvido pelas tools. Em tabelas Markdown, inclua o @<paciente_id> em uma coluna ou célula própria para não quebrar a formatação. Não invente ids.',
  claudeEvents: [],
  conversationId: uid(),
  claudeBusy: false,
  claudeError: null,
  unidades: [],
  unidadeSelecionada: 'all',
  unidadesLoading: false,
  unidadesErro: null,
  patientModalOpen: false,
  patientLoading: false,
  patientData: null,
  patientError: null,
  patientFocusId: null,

  init() {
    this.status = 'connected'
    this.statusMessage = 'Chat pronto'
    this.loadUnidades()
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

  isCollapsible(event) {
    const type = event?.type
    return ['COMPLETE', 'TOOL_CALL', 'TOOL_RESULT'].includes(type)
  },

  handleTimelineClick(event) {
    const target = event?.target?.closest('[data-patient-id]')
    if (!target) return
    const patientId = target.dataset.patientId
    if (!patientId) return
    event.preventDefault()
    this.showPatientModal(patientId)
  },

  handleTimelineKeydown(event) {
    const target = event?.target?.closest('[data-patient-id]')
    if (!target) return
    if (event.key !== 'Enter' && event.key !== ' ') return
    const patientId = target.dataset.patientId
    if (!patientId) return
    event.preventDefault()
    this.showPatientModal(patientId)
  },

  scrollToBottom() {
    const box = this.$refs?.timeline
    if (!box) return
    box.scrollTop = box.scrollHeight
  },

  async newConversation() {
    const previousId = this.conversationId
    this.conversationId = uid()
    this.claudeEvents = []
    this.claudePrompt = ''
    this.claudeError = null
    this.status = 'connected'
    this.statusMessage = 'Nova conversa iniciada'

    if (!previousId) return
    try {
      await fetch('/api/claude/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conversation_id: previousId }),
      })
    } catch (err) {
      console.warn('Não foi possível limpar a conversa anterior', err)
    }
  },

  async loadUnidades() {
    this.unidadesErro = null
    this.unidadesLoading = true
    try {
      const res = await fetch('/api/unidades')
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data?.detail || 'Falha ao carregar unidades')
      }
      this.unidades = Array.isArray(data.unidades) ? data.unidades : []
    } catch (err) {
      this.unidadesErro = err.message
    } finally {
      this.unidadesLoading = false
    }
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

    const promptBase = this.claudePrompt.trim()
    let prompt = promptBase

    if (this.unidadeSelecionada && this.unidadeSelecionada !== 'all') {
      const selected = this.unidades.find(
        (u) => String(u.unidade_id) === String(this.unidadeSelecionada)
      )
      const unitId = selected?.unidade_id || this.unidadeSelecionada
      const unitLabelParts = [`ID ${unitId}`]
      if (selected?.cnes) unitLabelParts.push(`CNES ${selected.cnes}`)
      const unitLabel = `${selected?.name || 'Unidade selecionada'} (${unitLabelParts.join(', ')})`
      prompt = `${promptBase}\n\n[Filtro de unidade selecionado: ${unitLabel}. Ao chamar tools, use unidade_saude_id=${unitId}.]`
    }

    this.claudeBusy = true
    this.status = 'connecting'
    this.statusMessage = 'Chamando Claude...'

    try {
      const res = await fetch('/api/claude/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: this.claudeApiKey,
          model: this.claudeModel,
          prompt,
          system_prompt: this.claudeSystem,
          max_turns: 4,
          tool_alias: 'pec',
          conversation_id: this.conversationId,
        }),
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data?.detail || 'Falha ao executar o chat')
      }
      if (data.conversation_id) {
        this.conversationId = data.conversation_id
      }
      if (Array.isArray(data.events)) {
        this.claudeEvents = [...this.claudeEvents, ...data.events]
        this.$nextTick(() => this.scrollToBottom())
      }
      this.status = 'connected'
      this.statusMessage = 'Resposta recebida'
      this.claudePrompt = ''
    } catch (err) {
      this.claudeError = err.message
      this.status = 'error'
      this.statusMessage = 'Erro na execução'
    } finally {
      this.claudeBusy = false
    }
  },

  closePatientModal() {
    this.patientModalOpen = false
    this.patientData = null
    this.patientError = null
    this.patientFocusId = null
  },

  async showPatientModal(patientId) {
    this.patientModalOpen = true
    this.patientLoading = true
    this.patientError = null
    this.patientData = null
    this.patientFocusId = patientId
    try {
      const res = await fetch(`/api/pacientes/${patientId}`)
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data?.detail || 'Falha ao carregar paciente')
      }
      this.patientData = data.paciente
    } catch (err) {
      this.patientError = err.message
    } finally {
      this.patientLoading = false
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
