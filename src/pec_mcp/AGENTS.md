# PEC-MCP – Regras Locais do Módulo `pec_mcp`

## Objetivo
- Este módulo implementa tools MCP de consulta clínica em modo somente leitura.
- O padrão obrigatório é minimização de dados: retornar apenas o mínimo necessário para responder à pergunta clínica.

## Regra absoluta de privacidade
- Jamais, em nenhuma circunstância, exponha o nome completo de pacientes em payloads de tools, exemplos, logs, mensagens de erro, documentação, testes ou respostas do agente.
- Se a query precisar ler `tb_cidadao.no_cidadao` para filtrar ou derivar iniciais, esse valor não pode sair do processo nem ser serializado na resposta.
- O retorno público deve usar apenas dados anonimizados ou estritamente necessários ao caso de uso.

## Dados que não podem ser expostos
- Nome completo da paciente ou do paciente.
- CPF, CNS, telefone, e-mail, endereço, nome da mãe, CNS da equipe, prontuário local, documento, cartão ou qualquer identificador civil.
- Texto livre que contenha identificação direta ou que permita reidentificação óbvia.
- Combinações desnecessárias de atributos que aumentem risco de reidentificação quando não forem essenciais para a tool.

## Padrão de saída para pacientes
- Prefira `paciente_initials` em vez de nome.
- Use `paciente_id` apenas quando a tool exigir identificador interno para navegação clínica entre tools.
- Retorne datas em formato ISO quando necessárias ao caso de uso.
- Não inclua campos “por conveniência”. Todo campo exposto precisa ter justificativa funcional clara.

## Checklist obrigatório ao criar ou alterar tools
- Investigar primeiro o codebase de referência do PEC e registrar hipóteses concretas sobre schema e regras de negócio.
- Modelos em nuvem podem consultar somente metadados de schema. Nunca podem executar consultas que retornem ou derivem valores clínicos reais.
- Validar as hipóteses sobre dados reais exclusivamente com agente/modelo local em infraestrutura privada, usando conexão somente leitura e o protocolo de `docs/VALIDACAO_LOCAL_TOOLS.md`.
- Incorporar somente o relatório local sanitizado, sem linhas, valores clínicos, identificadores ou textos copiados do banco.
- Se a validação local ainda não tiver ocorrido, documentar a regra como não confirmada contra dados reais.
- Revisar se a SQL seleciona alguma coluna sensível sem necessidade. Se selecionar, remover.
- Revisar `TypedDict` e qualquer serialização para garantir que não exista campo de PII.
- Atualizar o `README.md` da tool com guardrails e campos retornados.
- Adicionar ou atualizar teste de regressão cobrindo ausência de PII no contrato e, quando aplicável, na SQL gerada.

## Regras de implementação
- Sempre projete explicitamente as colunas do `SELECT`; nunca use `SELECT *`.
- Nunca retorne `no_cidadao` no resultado de uma tool.
- Se precisar do nome para derivar iniciais, converta para iniciais no servidor e descarte o valor bruto antes da resposta.
- Evite joins em tabelas ou colunas de identificação direta quando não forem necessários para o caso de uso.
- Limite paginação e quantidade de registros por padrão para reduzir risco de vazamento massivo.
- Preserve o caráter somente leitura: sem `INSERT`, `UPDATE`, `DELETE`, `UPSERT`, `ALTER`, `CREATE`, `DROP` ou qualquer mutação.
- Ignore registros de `tb_atend_prof` com `st_cancelado = 1` em tools que representam atendimentos clínicos concluídos ou válidos.

## Regras de testes
- Toda tool que retorna dados de paciente deve ter teste verificando que o payload não contém `nome_paciente`, `no_cidadao` ou equivalente.
- Quando houver geração de SQL dinâmica, o teste deve verificar que a SQL não projeta colunas sensíveis sem necessidade.
- Ao corrigir um vazamento, adicione teste de regressão no mesmo change set.

## Documentação
- Cada tool deve ter documentação própria em `tools/docs/<tool>/README.md` ou no README consolidado de tools.
- A documentação deve deixar explícito:
- Quais tabelas e colunas são acessadas.
- Quais campos são retornados.
- Quais guardrails de privacidade foram aplicados.
- Se uma tool usa nome apenas internamente para filtro ou derivação de iniciais, isso deve ser documentado sem expor exemplos com nomes reais.

## Em caso de dúvida
- Se houver dúvida entre utilidade e privacidade, escolha privacidade.
- Se uma necessidade funcional parecer exigir PII direta, pare e redesenhe a tool para anonimizar ou reduzir o escopo.
