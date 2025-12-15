# Tool: capturar_paciente

- **Descrição**: retorna dados mínimos de pacientes de forma anonimizada (iniciais, data de nascimento, sexo/gênero) usando filtros obrigatórios para evitar varreduras.
- **Consulta**: somente leitura.
- **Tabelas/colunas relevantes**:
  - `tb_cidadao`:
    - `co_seq_cidadao` (PK interna)
    - `no_cidadao` (usado apenas para gerar iniciais)
    - `dt_nascimento` (cálculo de idade/data de nascimento)
    - `no_sexo` (sexo, também usado como `gender` por fallback) — valores típicos: `MASCULINO`, `FEMININO`, `INDETERMINADO`
- **Filtros suportados**:
  - `paciente_id` (co_seq_cidadao)
  - `name_starts_with` (prefixo de nome, ILIKE)
  - `sex` (ex.: `MASCULINO`/`FEMININO`/`INDETERMINADO` ou aliases `M`/`F`/`I`)
  - `age_min` / `age_max` (anos, via `DATE_PART('year', AGE(...))`)
  - `limite` (1–200; default 50)
- **Guardrails**:
  - Exige pelo menos um critério (id, prefixo, sexo ou idade) antes de consultar.
  - Retorno traz apenas iniciais, nunca nome completo ou documentos.
  - Limite máximo de 200 linhas para evitar vazamento massivo.
