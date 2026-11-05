# BairroIQ | Materialização física Frontend v1 — contrato protegido

## Estado

O runner `barrioiq_pipeline/frontend_v1_delta_runner.py` é uma entrega **interna** que cria, sob confirmação manual, `workspace.gold.bairroiq_frontend_v1`. Não altera as sete tabelas Delta de origem nem a Gold Wide, não publica o dado, não cria API, não modifica grants e não configura Job automático. A revisão de permissões ficou para a homologação coletiva, antes da apresentação.

## Grão e fonte

- Uma linha por `(snapshot_id, cd_dist)`, exatamente **96 distritos oficiais** do IBGE; um único snapshot v1 é aceito na tabela.
- Snapshot: `v3.0.0-candidato|726091fefefa868fd5d0d2c6929b1d68c4849941f4c7510b4fee0d93a075d38b`.
- Fonte: `frontend_v1_runner.run_from_spark`, que executa preflight estrito sobre as sete tabelas físicas Star Schema, sem extrair LED da Gold Wide.
- `publicacao_autorizada=false` em todas as linhas. Perfis K-Means v3 são **candidatos, não homologados**. `Segurança` permanece uma proxy relativa a roubos/furtos, **não risco individual**.
- Snapshot é versão do dado/modelo, **não o ano de referência dos indicadores**. Empregos referem-se a 2021; os demais devem preservar limitações das fontes.

## Campos físicos (13)

| Campo | Tipo Spark | Uso |
|---|---|---|
| `snapshot_id` | STRING | Identificador do snapshot de dados/modelo |
| `cd_dist` | BIGINT | Chave oficial do distrito |
| `distrito` | STRING | Nome oficial |
| `latitude` | DOUBLE | Centroide distrital |
| `longitude` | DOUBLE | Centroide distrital |
| `perfil_id` | STRING | Código completo do K-Means v3 |
| `cluster` | STRING | P01–P09 + rótulo provisório |
| `empregos` | DOUBLE | Percentil relativo entre 96 distritos, 0–100 |
| `roubos` | DOUBLE | Registros por 1.000 habitantes |
| `seguranca` | DOUBLE | Índice inverso relativo de registros, 0–100 |
| `mobilidade` | DOUBLE | Média de percentis relativos dos equipamentos, 0–100 |
| `tipo_territorio` | STRING | Sempre DISTRITO_IBGE |
| `publicacao_autorizada` | BOOLEAN | Sempre false |

O frontend lê esses nomes técnicos e exibe `Distrito | Empregos | Roubos | Segurança | Mobilidade | Cluster`.

## Mecanismos de proteção

- `check(spark)` é **somente leitura**. Confere o contrato completo, gera um `payload_sha256` determinístico dos 96 registros, detecta tabela ausente/existente e prepara a ação provável (`APPEND_SNAPSHOT` ou `KEEP_VERIFIED`).
- `apply_snapshot(spark, confirmation=..., expected_snapshot_id=..., expected_payload_sha256=...)` exige confirmação literal, versão e hash devolvido pelo `check`. Uma divergência bloqueia **antes de gravar**.
- Apenas `.format('delta').mode('append').saveAsTable()` é utilizado. Não usa overwrite, delete, merge, replace, grants ou publicação externa.
- Uma segunda execução com os mesmos 96 registros é idempotente e retorna `ALREADY_MATERIALIZED_AND_VERIFIED`, sem gravar novamente.
- Se a tabela já existe com outro snapshot, schema incorreto, cardinalidade parcial ou conteúdo divergente, a execução falha de forma conservadora.
- Apenas **um operador** deve executar o `apply_snapshot` por vez; o padrão append/check não é um bloqueio distribuído contra concorrência.

## Critérios de aceite

1. CI do módulo, testes sintéticos e validação de Bundle aprovados.
2. Deploy carrega o runner no workspace preservando os sete Jobs existentes.
3. `check(spark)` retorna 96 previstos, `will_write_on_check=false`, `publicacao_autorizada=false` e SHA256 do payload.
4. Após aprovação manual, única execução controlada de `apply_snapshot`.
5. Novo `check(spark)` retorna `KEEP_VERIFIED`, `rows_in_snapshot=96` e mesmo hash.
6. Nenhuma modificação em `workspace.gold.distritos_wide` ou nas sete tabelas do Star Schema.

**Importante:** uma marca lógica de não publicação não equivale a isolamento de permissões. A validação de acesso permanece etapa separada da homologação do grupo, conforme combinado.
