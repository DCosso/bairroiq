# BairroIQ — Contrato frontend v1 (prévia somente leitura)

## Estado

Código interno e exploratório, com validações executáveis. **Não cria a tabela física nem faz publicação.** Esta etapa registra o contrato do frontend para validação dos integrantes do grupo. A revisão de permissões será realizada na homologação coletiva antes da apresentação final.

## Fonte e granularidade

- Uma linha por **distrito administrativo oficial IBGE**, com rótulo visual **Distrito**; não representa bairros imobiliários.
- `snapshot_id` fixo: `v3.0.0-candidato|726091fefefa868fd5d0d2c6929b1d68c4849941f4c7510b4fee0d93a075d38b`.
- Fonte principal: sete tabelas físicas `workspace.gold.bairroiq_*`, com preflight estrito `star_schema_v1_delta_runner.check(spark)`.
- Fonte adicional: `workspace.gold.distritos_wide`, coluna **real** `obs_porcentagem_de_lampadas_led_na_iluminacao_p_a1e1d34b` (percentual ObservaSampa).
- A Gold Wide não possui datas de referência uniformes. O snapshot do modelo **não representa a data dos dados**.
- **Atenção ao LED:** esta coluna vem da Gold Wide atual e **não faz parte dos 11 indicadores cujo hash foi congelado pelo ML v3**. O preflight do Delta não fixa sozinho os valores de LED. Antes de uma escrita física, capturar e fixar a versão Delta dessa fonte e conciliar a distribuição/valores para assegurar reprodutibilidade.

## Oito colunas visuais, na ordem

| Coluna | Tipo / cálculo | Unidade e ressalva |
|---|---|---|
| Distrito | `NM_DIST` oficial | Distrito administrativo IBGE, não bairro imobiliário |
| Empregos | `percent_rank` do total de empregos formais entre os 96 distritos | Índice relativo 0–100, dados ObservaSampa/RAIS 2021; não são vagas disponíveis |
| Roubos | `roubos` (taxa por 100 mil) / 100 | Registros por 1.000 habitantes, janela 12m, fim não catalogado |
| Segurança | `100 - indice_ordenacao_ocorrencias` | Proxy relativa baseada em roubo e furto; **não mede segurança geral nem risco individual** |
| Iluminação LED | Indicador ObservaSampa percentual da Gold, com 1 decimal | Percentual real, 0–100; referência temporal não homologada |
| Arborização | `NULL` | Sem indicador direto validado; não substituir por praça/corredor verde |
| Mobilidade | Média dos `percent_rank` de metrô, ônibus e trem por 10 mil hab. | Proxy relativa 0–100; não equivale ao tempo de deslocamento |
| Cluster | `P01` a `P09` + nome provisório do K-Means v3 | Classificação exploratória, não recomendação residencial |

## Campo técnico

`snapshot_id`, `cd_dist`, `distrito`, `latitude`, `longitude`, `perfil_id`, `cluster`, `empregos`, `roubos`, `seguranca`, `iluminacao_led`, `arborizacao`, `mobilidade`, `tipo_territorio`, `publicacao_autorizada`.

`publicacao_autorizada` permanece `false` até homologação do grupo. A leitura interna e validação por grupo não significam liberação pública. O frontend deve dispor de rótulos explicativos e fontes para cada métrica; não misturar taxas brutas, índices relativos e porcentagens em uma mesma escala visual sem legenda.

## Cobertura real da prévia de 05/11/2026

A execução do notebook fornecida pelo grupo retornou 96 distritos, nove clusters, 96 LEDs preenchidos e nenhum valor de arborização. A auditoria dos CSVs exportados identificou 81/96 distritos com LED igual a 100%, média ~99,87%; portanto LED pode ter baixo poder discriminatório.

## Bloqueios

- Nenhuma escrita Delta, job, view, arquivo ou API feita pelo módulo.
- Falha se o snapshot divergir, a Gold divergir do preflight, a cardinalidade mudar, houver chaves duplicadas ou perfil público, ou se um indicador obrigatório ficar nulo/inválido.
- A materialização futura, se aprovada, requer **outro PR**, destino físico definido, modo `check` prévio e mecanismo de publicação separado.
- O aviso de Window sem partição do notebook inicial foi eliminado nesta versão usando cálculo `percent_rank` em pandas para apenas 96 registros; mantém semântica dos empates do Spark, e usa arredondamento decimal `ROUND_HALF_UP` para reproduzir `F.round`.

## Escopo acadêmico

Briefing Hands-On Mackenzie: Lakehouse, Wide Table, Star Schema, CI/CD, IaC, arquitetura Lambda e MVP visual funcional. O modelo dimensional está validado; a Lambda e o MVP visual são entregas separadas, ainda pendentes.
