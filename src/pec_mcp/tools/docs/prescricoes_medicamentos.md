# `listar_prescricoes_medicamentos`

## Finalidade

Lista o histórico estruturado de prescrições de um paciente para análises
longitudinais de início, ajuste, renovação, conclusão e interrupção. É uma
consulta somente leitura e não substitui reconciliação medicamentosa ou decisão
clínica.

## Fontes e campos

- `tb_receita_medicamento`: item prescrito, doses, frequência, posologia,
  vigência, uso contínuo, recomendação, interrupção e grupo de renovação;
- `tb_medicamento`: princípio ativo, concentração e unidade de fornecimento;
- `tb_atend_prof` e `tb_atend`: vínculo e data do atendimento;
- `tb_prontuario`: paciente e grupo de prontuários;
- `tb_cid10` e `tb_ciap`: motivo codificado, quando existente.

A consulta usa `COALESCE(co_prontuario_grupo, co_seq_prontuario)` para abranger
registros unificados e exclui `tb_atend_prof.st_cancelado = 1`.

## Contrato e guardrails

- `paciente_id` é obrigatório; `estado`, `medicamento` e `limite` são opcionais;
- `limite` é restrito a 1–500;
- interrupção prevalece sobre a data final ao calcular o estado;
- dose geral, doses por turno, frequência, posologia e recomendação livre
  permanecem em campos separados;
- HTML da recomendação é removido, preservando quebras de linha;
- `alerta_consistencia_documental` sinaliza recomendação com turno sem as doses
  estruturadas correspondentes, mas não escolhe qual registro está correto;
- não retorna nome, CPF, CNS, endereço nem identificadores externos.

## Validação local

As relações, regras de vigência, prontuários agrupados, atendimento cancelado,
uso contínuo e campos estruturados foram confirmados por validação local
sanitizada em 2026-07-20, documentada em
`docs/HIPOTESES_PRESCRICAO_MEDICAMENTOS.md`. Os testes unitários verificam
agrupamento, exclusão de cancelados, sanitização, alerta documental e
precedência da interrupção sem consultar dados clínicos reais.

Pendência preservada: variações históricas do encadeamento de renovação podem
não identificar de forma inequívoca a última receita; por isso o histórico não
descarta receitas anteriores do mesmo grupo.
