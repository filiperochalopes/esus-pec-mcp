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

const readChatDefaults = () => {
  const el = document.getElementById('chat-defaults')
  if (!el) return {}
  try {
    return JSON.parse(el.textContent || '{}')
  } catch (err) {
    console.warn('Não foi possível ler defaults do Chat', err)
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

  componentLabel(letter) {
    const map = {
      A: 'A — 1ª consulta até 12ª semana',
      B: 'B — ≥7 consultas no pré-natal',
      C: 'C — ≥7 aferições de PA',
      D: 'D — ≥7 registros peso+altura',
      E: 'E — ≥3 visitas domiciliares gestante',
      F: 'F — dTpa após 20ª semana',
    }
    return map[letter] || letter
  },

  async loadSaude360Detail(component, unidade) {
    this.saude360DetailError = null
    this.saude360DetailLoading = true
    this.saude360DetailComponent = component
    this.saude360DetailUnit = unidade || null
    this.saude360DetailOpen = true
    const params = new URLSearchParams()
    if (this.saude360Filters.startDate) params.set('start_date', this.saude360Filters.startDate)
    if (this.saude360Filters.endDate) params.set('end_date', this.saude360Filters.endDate)
    if (unidade?.unidade_id) params.set('unidade_id', unidade.unidade_id)
    params.set('page', (this.saude360DetailData?.page || 1).toString())
    params.set('page_size', (this.saude360DetailData?.page_size || 25).toString())
    try {
      const res = await fetch(`/saude-360/c3/${component}?${params.toString()}`)
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data?.detail || 'Falha ao carregar detalhes')
      }
      this.saude360DetailData = data
    } catch (err) {
      this.saude360DetailError = err.message
    } finally {
      this.saude360DetailLoading = false
    }
  },

  async openSaude360Detail(component, unidade) {
    this.saude360DetailData = { page: 1, page_size: 25 }
    await this.loadSaude360Detail(component, unidade)
  },

  async detailPrevPage() {
    if (!this.saude360DetailData || this.saude360DetailLoading) return
    if (this.saude360DetailData.page <= 1) return
    this.saude360DetailData.page -= 1
    await this.loadSaude360Detail(this.saude360DetailComponent, this.saude360DetailUnit)
  },

  async detailNextPage() {
    if (!this.saude360DetailData || this.saude360DetailLoading) return
    const totalPages = this.saude360DetailData.total_pages || 0
    if (totalPages && this.saude360DetailData.page >= totalPages) return
    this.saude360DetailData.page += 1
    await this.loadSaude360Detail(this.saude360DetailComponent, this.saude360DetailUnit)
  },

  detailInfo(component, item) {
    switch (component) {
      case 'A':
        return item.primeira_consulta
          ? `Primeira consulta em ${item.primeira_consulta}`
          : 'Sem 1ª consulta até 12ª semana'
      case 'B':
        return `Consultas registradas: ${item.total_consultas}/7`
      case 'C':
        return `PA registradas: ${item.total_pa}/7`
      case 'D':
        return `Peso+altura: ${item.total_antropometria}/7`
      case 'E':
        return `Visitas gestante: ${item.total_visitas}/3`
      case 'F':
        return item.tem_dtpa ? 'dTpa registrada' : 'Sem dTpa ≥20ª semana'
      default:
        return ''
    }
  },

  // State Variables
  chatProvider: readChatDefaults().provider || 'anthropic',
  chatApiKey: readChatDefaults().api_key || '',
  chatModel: readChatDefaults().model || 'claude-3-5-sonnet-20241022',
  chatApiBase: readChatDefaults().api_base || '',
  chatPrompt: '',
  chatSystem:
    'Você é um agente clínico que usa tools MCP para recuperar dados. Sempre que responder com pacientes (lista ou item), acrescente o identificador real no formato @<paciente_id> usando o co_seq_cidadao devolvido pelas tools. Em tabelas Markdown, inclua o @<paciente_id> em uma coluna ou célula própria para não quebrar a formatação. Não invente ids.',
  chatEvents: [],
  conversationId: uid(),
  chatBusy: false,
  chatError: null,
  
  unidades: [],
  unidadeSelecionada: 'all',
  unidadesLoading: false,
  unidadesErro: null,
  
  autoToolMenuOpen: false,
  autoToolInputOpen: false,
  autoToolArgument: '',
  autoToolError: null,
  autoTools: [
    { id: 'paciente-id', label: '/paciente-id', description: 'Abrir detalhes e histórico SOAP pelo id interno.', active: true },
    { id: 'paciente-cpf', label: '/paciente-cpf', description: 'Breve', active: false },
    { id: 'gestantes', label: '/gestantes', description: 'Breve', active: false },
    { id: 'gestante-cpf', label: '/gestante-cpf', description: 'Breve', active: false },
    { id: 'gestante-id', label: '/gestante-id', description: 'Breve', active: false },
    {
      id: 'saude-360-c3',
      label: '/saude-360-c3',
      description: 'Abrir tabela do indicador C3 (gestantes/puérperas) por unidade, sem usar LLM.',
      active: true,
    },
  ],
  
  patientModalOpen: false,
  patientLoading: false,
  patientData: null,
  patientError: null,
  patientFocusId: null,
  patientHistory: [],
  patientHistorySummary: '',
  patientHistorySummaryShort: '',
  patientHistoryLoading: false,
  patientHistoryLoaded: false,
  patientHistoryOpen: false,
  patientHistoryError: null,
  patientConditions: [],
  patientConditionsLoading: false,
  patientConditionsLoaded: false,
  patientConditionsOpen: false,
  patientConditionsError: null,
  summaryPreparing: false,
  
  saude360ModalOpen: false,
  saude360Loading: false,
  saude360Error: null,
  saude360Data: null,
  saude360Filters: {
    startDate: '',
    endDate: '',
  },
  saude360DetailOpen: false,
  saude360DetailLoading: false,
  saude360DetailError: null,
  saude360DetailData: null,
  saude360DetailComponent: null,
  saude360DetailUnit: null,
  
  toolsModalOpen: false,
  toolsInfo: [
    {
      id: 'capturar_paciente',
      name: 'capturar_paciente',
      scope: 'somente leitura',
      description: 'Dados mínimos do paciente (iniciais, data de nascimento, sexo/genero) com filtros obrigatorios.',
      filters: 'Requer id, prefixo, sexo ou faixa etaria; aceita unidade_saude_id; limite 200.',
    },
    {
      id: 'obter_codigos_condicao_saude',
      name: 'obter_codigos_condicao_saude',
      scope: 'somente leitura',
      description: 'Mapeia uma condicao de saude para codigos CID/CIAP (presets + busca por nome).',
      filters: 'Use antes de filtrar por condicao; limite 200 por sistema.',
    },
    {
      id: 'listar_condicoes_pacientes',
      name: 'listar_condicoes_pacientes',
      scope: 'somente leitura',
      description: 'Somente para listar condicoes CID/CIAP registradas em pacientes com ultima evolucao/observacao. Nao use para descobrir codigos.',
      filters: 'Precisa de ao menos um filtro (paciente, nome, sexo, idade ou CID/CIAP/texto); limite 200.',
    },
    {
      id: 'contar_pacientes',
      name: 'contar_pacientes',
      scope: 'somente leitura',
      description: 'Retorna somente a contagem de pacientes distintos pelos filtros de paciente/condição.',
      filters: 'Exige pelo menos um critério; suporta AND/OR em múltiplos CIDs; sem payload de pacientes.',
    },
    {
      id: 'contar_pacientes_sem_consulta',
      name: 'contar_pacientes_sem_consulta',
      scope: 'somente leitura',
      description: 'Conta hipertensos/diabéticos/gestantes sem consulta recente com médico/enfermeiro.',
      filters: 'Obrigatório tipo; dias_sem_consulta (default 180/60); unidade_saude_id opcional.',
    },
    {
      id: 'listar_pacientes_sem_consulta',
      name: 'listar_pacientes_sem_consulta',
      scope: 'somente leitura',
      description: 'Lista pacientes sem consulta recente por condição (hipertensão/diabetes/gestação) com paginação.',
      filters: 'Obrigatório tipo; limite/offset; retorna iniciais, data de nascimento, sexo e última consulta.',
    },
    {
      id: 'listar_unidades_saude',
      name: 'listar_unidades_saude',
      scope: 'somente leitura',
      description: 'Lista unidades (id interno, CNES, nome) para popular selects e filtros.',
      filters: 'Sem filtros; apenas lista todas as unidades ativas.',
    },
    {
      id: 'listar_ultimos_atendimentos_soap',
      name: 'listar_ultimos_atendimentos_soap',
      scope: 'somente leitura',
      description: 'Últimos atendimentos SOAP de um paciente específico, com profissional e CBO.',
      filters: 'Obrigatório paciente_id; médicos/enfermeiros (CBO 225%/2235%); limite opcional até 1000.',
    },
  ],

  init() {
    this.status = 'connected'
    this.statusMessage = 'Chat pronto'
    this.loadUnidades()
  },

  formatTs(ts) {
    return new Date(ts).toLocaleTimeString()
  },

  formatDateTime(ts) {
    if (!ts) return 'Sem data'
    try {
      return new Date(ts).toLocaleString()
    } catch (err) {
      return String(ts)
    }
  },

  formatJson(value) {
    return prettyJson(value)
  },

  renderMarkdown(text) {
    return renderMarkdown(text)
  },

  formatScore(value) {
    const num = Number(value)
    if (Number.isNaN(num)) return '—'
    return num.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  },

  scoreClass(value) {
    const num = Number(value)
    if (Number.isNaN(num)) return 'text-slate-300'
    if (num > 75) return 'text-emerald-300'
    if (num > 50) return 'text-sky-300'
    if (num > 25) return 'text-amber-300'
    return 'text-rose-300'
  },

  saude360Rows() {
    if (!this.saude360Data || !Array.isArray(this.saude360Data.unidades)) return []
    const rows = [...this.saude360Data.unidades]
    const selected = this.unidadeSelecionada
    const filtered =
      selected && selected !== 'all'
        ? rows.filter((r) => String(r.unidade_id) === String(selected))
        : rows
    return filtered.sort((a, b) => {
      const av = Number(a?.score_c3 || 0)
      const bv = Number(b?.score_c3 || 0)
      return bv - av
    })
  },

  stripHtml(text) {
    if (!text) return ''
    const div = document.createElement('div')
    div.innerHTML = String(text)
    const clean = (div.textContent || div.innerText || '').replace(/\u00a0/g, ' ')
    return clean.replace(/\s+/g, ' ').trim()
  },

  isCollapsible(event) {
    const type = event?.type
    return ['COMPLETE', 'TOOL_CALL', 'TOOL_RESULT'].includes(type)
  },

  handlePromptKeydown(event) {
    if (event.key === '/') {
      this.autoToolMenuOpen = true
    } else if (event.key === 'Escape' && this.autoToolMenuOpen) {
      this.autoToolMenuOpen = false
    }
  },

  handlePromptInput(event) {
    if (this.autoToolMenuOpen && !event.target.value.includes('/')) {
      this.autoToolMenuOpen = false
    }
  },

  selectAutoTool(tool) {
    if (!tool || !tool.active) return
    if (tool.id === 'paciente-id') {
      this.autoToolMenuOpen = false
      this.autoToolInputOpen = true
      this.autoToolArgument = ''
      this.autoToolError = null
      this.$nextTick(() => {
        const input = this.$refs?.autoToolInput
        if (input?.focus) input.focus()
      })
    } else if (tool.id === 'saude-360-c3') {
      this.autoToolMenuOpen = false
      this.loadSaude360C3()
    }
  },

  cancelAutoToolInput() {
    this.autoToolInputOpen = false
    this.autoToolArgument = ''
    this.autoToolError = null
  },

  async confirmPacienteAutoTool() {
    const parsed = parseInt(this.autoToolArgument, 10)
    if (!parsed || Number.isNaN(parsed)) {
      this.autoToolError = 'Informe um id numérico.'
      return
    }
    this.autoToolInputOpen = false
    this.autoToolArgument = ''
    this.autoToolError = null
    await this.showPatientModal(parsed)
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
    this.chatEvents = []
    this.chatPrompt = ''
    this.chatError = null
    this.status = 'connected'
    this.statusMessage = 'Nova conversa iniciada'

    if (!previousId) return
    try {
      await fetch('/api/chat/reset', {
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

  async loadSaude360C3() {
    if (this.saude360Loading) return
    this.saude360Error = null
    this.saude360Loading = true
    this.saude360ModalOpen = true
    const params = new URLSearchParams()
    if (this.saude360Filters.startDate) params.set('start_date', this.saude360Filters.startDate)
    if (this.saude360Filters.endDate) params.set('end_date', this.saude360Filters.endDate)
    if (this.unidadeSelecionada && this.unidadeSelecionada !== 'all') {
      params.set('unidade_id', this.unidadeSelecionada)
    }
    const qs = params.toString()
    try {
      const res = await fetch(`/saude-360/c3${qs ? `?${qs}` : ''}`)
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data?.detail || 'Falha ao calcular indicador C3')
      }
      this.saude360Data = data
      this.saude360ModalOpen = true
    } catch (err) {
      this.saude360Error = err.message
    } finally {
      this.saude360Loading = false
      this.autoToolMenuOpen = false
    }
  },

  closeSaude360Modal() {
    this.saude360ModalOpen = false
    this.saude360Error = null
    this.saude360DetailOpen = false
    this.saude360DetailData = null
    this.saude360DetailError = null
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

  async runChat() {
    if (this.chatBusy) return
    this.chatError = null
    
    // Check key only if provider is not ollama (which might not need it)
    if (this.chatProvider !== 'ollama' && !this.chatApiKey) {
      this.chatError = 'Informe sua API Key.'
      return
    }
    if (!this.chatPrompt.trim()) {
      this.chatError = 'Digite um prompt.'
      return
    }

    const promptBase = this.chatPrompt.trim()
    let prompt = promptBase

    if (promptBase === '/saude-360-c3') {
      this.chatPrompt = ''
      this.autoToolMenuOpen = false
      this.loadSaude360C3()
      return
    }

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

    this.chatBusy = true
    this.status = 'connecting'
    this.statusMessage = 'Chamando LLM...'

    try {
      const res = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: this.chatProvider,
          api_key: this.chatApiKey,
          api_base: this.chatApiBase,
          model: this.chatModel,
          prompt,
          system_prompt: this.chatSystem,
          max_turns: 4,
          tool_alias: 'pec',
          conversation_id: this.conversationId,
        }),
      })
      if (!res.ok) {
        let detail = 'Falha ao executar o chat'
        try {
          const data = await res.json()
          detail = data?.detail || detail
        } catch (err) {
          // ignore parsing errors
        }
        throw new Error(detail)
      }
      if (!res.body) {
        throw new Error('Streaming indisponível no navegador.')
      }
      const reader = res.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''

      const handleLine = (line) => {
        const trimmed = line.trim()
        if (!trimmed) return
        let payload
        try {
          payload = JSON.parse(trimmed)
        } catch (err) {
          return
        }
        if (payload?.event) {
          this.chatEvents = [...this.chatEvents, payload.event]
          this.$nextTick(() => this.scrollToBottom())
          return
        }
        if (payload?.conversation_id) {
          this.conversationId = payload.conversation_id
          return
        }
        if (payload?.error) {
          throw new Error(payload.error)
        }
      }

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        lines.forEach(handleLine)
      }

      if (buffer.trim()) {
        handleLine(buffer)
      }

      this.status = 'connected'
      this.statusMessage = 'Resposta recebida'
      this.chatPrompt = ''
    } catch (err) {
      this.chatError = err.message
      this.status = 'error'
      this.statusMessage = 'Erro na execução'
    } finally {
      this.chatBusy = false
    }
  },

  closePatientModal() {
    this.patientModalOpen = false
    this.patientData = null
    this.patientError = null
    this.patientFocusId = null
    this.patientHistory = []
    this.patientHistorySummary = ''
    this.patientHistorySummaryShort = ''
    this.patientHistoryError = null
    this.patientHistoryLoading = false
    this.patientHistoryLoaded = false
    this.patientHistoryOpen = false
    this.patientConditions = []
    this.patientConditionsError = null
    this.patientConditionsLoading = false
    this.patientConditionsLoaded = false
    this.patientConditionsOpen = false
    this.patientConditionsError = null
    this.summaryPreparing = false
  },

  async showPatientModal(patientId) {
    this.patientModalOpen = true
    this.patientLoading = true
    this.patientError = null
    this.patientHistoryError = null
    this.patientConditionsError = null
    this.patientData = null
    this.patientHistory = []
    this.patientHistorySummary = ''
    this.patientHistorySummaryShort = ''
    this.patientConditions = []
    this.patientFocusId = patientId
    try {
      const patientRes = await fetch(`/api/pacientes/${patientId}`)
      const patientJson = await patientRes.json()
      if (!patientRes.ok) {
        throw new Error(patientJson?.detail || 'Falha ao carregar paciente')
      }
      this.patientData = patientJson.paciente
    } catch (err) {
      this.patientError = err.message
    } finally {
      this.patientLoading = false
    }
  },

  async loadPatientHistory() {
    if (!this.patientFocusId || this.patientHistoryLoading) return
    this.patientHistoryLoading = true
    this.patientHistoryError = null
    try {
      const historyRes = await fetch(`/api/pacientes/${this.patientFocusId}/historico`)
      const historyJson = await historyRes.json()
      if (!historyRes.ok) {
        throw new Error(historyJson?.detail || 'Falha ao carregar histórico SOAP')
      }
      this.patientHistory = Array.isArray(historyJson.historico)
        ? historyJson.historico.map((h) => ({
            ...h,
            soap_s_clean: this.stripHtml(h.soap_s),
            soap_o_clean: this.stripHtml(h.soap_o),
            soap_a_clean: this.stripHtml(h.soap_a),
            soap_p_clean: this.stripHtml(h.soap_p),
            condicoes: Array.isArray(h.condicoes)
              ? h.condicoes.map((c) => ({
                  ...c,
                  observacao_clean: this.stripHtml(c.observacao),
                }))
              : [],
          }))
        : []
      this.patientHistorySummary = historyJson.resumo || ''
      this.patientHistorySummaryShort = (historyJson.resumo || '').split('\n')[0] || ''
      this.patientHistoryLoaded = true
    } catch (err) {
      this.patientHistoryError = err.message
    } finally {
      this.patientHistoryLoading = false
    }
  },

  async loadPatientConditions() {
    if (!this.patientFocusId || this.patientConditionsLoading) return
    this.patientConditionsLoading = true
    this.patientConditionsError = null
    try {
      const condRes = await fetch(`/api/pacientes/${this.patientFocusId}/condicoes?limite=200`)
      const condJson = await condRes.json()
      if (!condRes.ok) {
        throw new Error(condJson?.detail || 'Falha ao carregar condições')
      }
      this.patientConditions = Array.isArray(condJson.condicoes)
        ? condJson.condicoes.map((c) => ({
            ...c,
            observacao_clean: this.stripHtml(c.observacao),
          }))
        : []
      this.patientConditionsLoaded = true
    } catch (err) {
      this.patientConditionsError = err.message
    } finally {
      this.patientConditionsLoading = false
    }
  },

  async toggleHistorySection(open) {
    this.patientHistoryOpen = open
    if (open && !this.patientHistoryLoaded) {
      await this.loadPatientHistory()
    }
  },

  async toggleConditionsSection(open) {
    this.patientConditionsOpen = open
    if (open && !this.patientConditionsLoaded) {
      await this.loadPatientConditions()
    }
  },

  buildAndSendSummaryPrompt() {
    const id = this.patientFocusId
    if (!id) return

    const historyCompact = this.patientHistory.map((item) => ({
      data_hora: item.data_hora,
      profissional: item.profissional,
      cbo: item.cbo_descricao || item.cbo_codigo,
      s: item.soap_s_clean || item.soap_s,
      o: item.soap_o_clean || item.soap_o,
      a: item.soap_a_clean || item.soap_a,
      p: item.soap_p_clean || item.soap_p,
      condicoes: (item.condicoes || []).map((c) => ({
        condition_id: c.condition_id,
        cid: c.cid_code,
        cid_desc: c.cid_description,
        ciap: c.ciap_code,
        ciap_desc: c.ciap_description,
        observacao: c.observacao_clean || c.observacao,
        inicio: c.dt_inicio_condicao,
        fim: c.dt_fim_condicao,
        situacao: c.situacao_id,
      })),
    }))

    const condicoesCompact = this.patientConditions.map((c) => ({
      cid: c.cid_code || null,
      cid_desc: c.cid_description || null,
      ciap: c.ciap_code || null,
      ciap_desc: c.ciap_description || null,
      inicio: c.dt_inicio_condicao,
      fim: c.dt_fim_condicao,
      situacao: c.situacao_id,
      observacao: c.observacao,
    }))

    const promptLines = []
    promptLines.push(`Elabore um resumo clínico conciso do paciente @${id} em até 3 parágrafos, inspirado no International Patient Summary (IPS).`)
    promptLines.push(
      'Não use formato SOAP; faça um panorama longitudinal, incluindo problemas/condições (CID/CIAP), alergias/medicações se houver, e plano/cuidados relevantes.'
    )
    promptLines.push(
      "Adicione um bloco curto de 'História recente' descrevendo os últimos encontros (sintomas, avaliações, planos) com base nos dados abaixo. Omitir se não houver dados."
    )
    promptLines.push('Use apenas informações fornecidas; seções sem dados não devem aparecer.')
    promptLines.push('Dados (mais recentes primeiro):')
    promptLines.push('')
    promptLines.push('Atendimentos SOAP:')
    promptLines.push(JSON.stringify(historyCompact, null, 2))
    promptLines.push('')
    promptLines.push('Condições registradas:')
    promptLines.push(JSON.stringify(condicoesCompact, null, 2))

    this.chatPrompt = promptLines.join('\n')

    if (this.chatApiKey || this.chatProvider === 'ollama') {
      this.$nextTick(() => this.runChat())
    }
  },

  async summarizeHistory() {
    if (!this.patientFocusId) return
    this.summaryPreparing = true
    try {
      if (!this.patientHistoryLoaded) {
        await this.loadPatientHistory()
      }
      if (!this.patientConditionsLoaded) {
        await this.loadPatientConditions()
      }
      this.buildAndSendSummaryPrompt()
      this.closePatientModal()
    } finally {
      this.summaryPreparing = false
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
