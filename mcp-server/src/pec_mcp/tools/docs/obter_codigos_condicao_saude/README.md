# Tool: obter_codigos_condicao_saude

- **Descricao**: retorna codigos CID-10/CIAP associados a uma condicao de saude para uso em outros filtros.
- **Uso recomendado**: perguntas do tipo "quais CID/CIAP de X?" ou para montar filtros antes de listar pacientes/condicoes.
- **Consulta**: somente leitura.
- **Tabelas/colunas relevantes**:
  - `tb_cid10`: `nu_cid10`, `no_cid10`, `no_cid10_filtro`, `nu_cid10_filtro`
  - `tb_ciap`: `co_ciap`, `ds_ciap`, `ds_ciap_filtro`
- **Filtros suportados**:
  - `condicao` (obrigatorio; busca por nome/descricao normalizada)
  - `limite` (1-200; default 50; aplicado por sistema CID/CIAP)
- **Saida**:
  - `source`: `preset`, `database` ou `fallback`.
  - `cid_codes` / `ciap_codes`: listas de codigos para uso em outros filtros.
  - `cid` / `ciap`: listas detalhadas com `code` e `description`.
  - `fallback_condition_text`: preenchido quando nao ha match no banco.
- **Guardrails**:
  - `condicao` obrigatoria e com maximo de 100 caracteres.
  - Limite maximo de 200 resultados por consulta.
  - Quando nao ha match no banco, retorna `fallback_condition_text` para uso em `condition_text`.
- **Presets hardcoded**:
  - `gravidez`:
    - CIAP: `W03`, `W05`, `W71`, `W78`, `W79`, `W80`, `W81`, `W84`, `W85`
    - CID-10: `Z32.1`, `Z33`, `Z34.0`, `Z34.8`, `Z34.9`, `Z35.0`, `Z35.1`, `Z35.2`, `Z35.3`,
      `Z35.4`, `Z35.5`, `Z35.6`, `Z35.7`, `Z35.8`, `Z35.9`
  - `desfecho gestacao`:
    - CIAP: `W82`, `W83`, `W90`, `W91`, `W92`, `W93`
    - CID-10: `O02`, `O03`, `O05`, `O06`, `O04`, `Z30.3`, `O80`, `Z37.0`, `Z37.9`, `Z38`, `Z39`,
      `Z37.1`, `O42`, `O45`, `O60`, `O61`, `O62`, `O63`, `O64`, `O65`, `O66`, `O67`, `O68`, `O69`,
      `O70`, `O71`, `O73`, `O75.0`, `O75.1`, `O75.4`, `O75.5`, `O75.6`, `O75.7`, `O75.8`, `O75.9`,
      `O81`, `O82`, `O83`, `O84`, `Z37.2`, `Z37.5`, `Z37.3`, `Z37.4`, `Z37.6`, `Z37.7`
  - `diabetes`:
    - CIAP: `T89`, `T90`
    - CID-10: `E10`, `E11`, `E12`, `E13`, `E14`
  - `hipertensao`:
    - CIAP: `K86`, `K87`
    - CID-10: `I10`, `I11`, `I11.0`, `I11.9`, `I12`, `I12.0`, `I12.9`, `I13`, `I13.0`, `I13.1`,
      `I13.2`, `I13.9`, `I15`, `I15.0`, `I15.1`, `I15.2`, `I15.8`, `I15.9`
