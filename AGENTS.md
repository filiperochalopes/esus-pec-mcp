# PEC-MCP – Agente de Consulta Clínica (MVP)

## Overview
- Servidor MCP em Python para fornecer dados clínicos do PEC (somente leitura) a agentes LLM.
- MVP reduzido: apenas uma tool para captura anonimizada de paciente.
- Conexão única ao PostgreSQL, reutilizada pelas tools para reduzir latência.

## Tool disponível

### capturar_paciente
- Descrição: retorna dados mínimos de pacientes sem PII direta (somente leitura) a partir de filtros.
- Parâmetros (informe pelo menos um critério):
  - `paciente_id` (int, co_seq_cidadao)
  - `name_starts_with` (str, prefixo do nome, ex.: "A")
  - `sex` (str, ex.: "MASCULINO" / "FEMININO" / "INDETERMINADO"; aceita aliases M/F/I)
  - `age_min` / `age_max` (int, faixa etária em anos)
  - `limite` (int, default 50, máx 200)
- Saída (`PatientCaptureResult`):
  - `name`: iniciais do nome completo (ex.: \"Joao de Carvalho Lima\" -> \"JCL\")
  - `birth_date`: data de nascimento no formato ISO (YYYY-MM-DD)
  - `sex`: sexo (coluna `no_sexo`)
  - `gender`: igual ao sexo por enquanto (fallback até existir coluna dedicada)
- Exemplos de prompt:
  - "Recupere o paciente 123 com iniciais, data de nascimento e sexo."
  - "Liste até 5 pacientes cujo nome começa com A, sexo masculino e idade mínima de 40 anos."

## Limitações
- Somente leitura; sem escrita ou alteração de dados clínicos.
- Resposta não inclui identificadores diretos (sem nomes completos ou IDs externos).
- Gender usa o mesmo valor de sexo até haver coluna dedicada.

## Segurança e privacidade
- Não exponha identificadores sensíveis em canais não autorizados.
- Utiliza iniciais para evitar exposição de nomes completos.
- Utilize limites e filtros estritos ao iterar sobre pacientes.

## Organização e documentação
- Diretório raiz do servidor MCP: `mcp-server/` (evite `src/` ou `pec_mcp/` adicionais que só adicionem aninhamento).
- Cada tool deve ter um `README.md` próprio descrevendo tabelas e colunas relevantes acessadas no banco, bem como quaisquer filtros ou guardrails aplicados.
