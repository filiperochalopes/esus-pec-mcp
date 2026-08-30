# `listar_resultados_hba1c`

## Finalidade

Lista resultados estruturados de hemoglobina glicada (HbA1c) de um paciente
para acompanhamento longitudinal e correlação temporal com HGT e mudanças
documentadas de prescrição.

## Fontes e campos

- `tb_exame_hemoglobina_glicada.vl_hemoglobina_glicada`;
- `tb_exame_requisitado.dt_realizacao` e `dt_resultado`;
- `tb_prontuario.co_cidadao` e `co_prontuario_grupo`.

## Contrato e guardrails

- `paciente_id` é obrigatório;
- `data_inicio`, `data_fim` e `limite` são opcionais;
- `limite` é restrito a 1–200;
- resultados são ordenados da referência mais recente para a mais antiga;
- prontuários agrupados são abrangidos;
- não retorna nome ou outro identificador direto;
- a tool fornece fatos temporais; não atribui causalidade a uma mudança
  medicamentosa.

## Validação local

O caminho `tb_exame_hemoglobina_glicada -> tb_exame_requisitado ->
tb_prontuario` já é usado pela consulta analítica de HbA1c do projeto. O teste
unitário valida filtros, limite e conversão do valor sem acessar dados reais.
Permanece necessário validar em cada instalação se resultados legados foram
migrados para as mesmas tabelas.
