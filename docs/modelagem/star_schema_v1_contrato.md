# BairroIQ — Contrato dimensional v1 (prévia somente leitura)

## Escopo

A Gold atual (`workspace.gold.distritos_wide`, 96 linhas) é uma **fotografia analítica** sem ano da fonte em cada métrica. O preview cria uma **constelação de fatos com dimensões conformadas** em pandas; não publica Delta, views ou API e não modifica o ML v3.

**Hash obrigatório:** `726091fefefa868fd5d0d2c6929b1d68c4849941f4c7510b4fee0d93a075d38b`. O pipeline v3 deve reproduzir as mesmas composições e métrica antes de gerar fatos. A execução é fail-closed se o hash ou outro contrato divergir.

## Diagrama lógico

```text
                      dim_snapshot (1)
                             |
             +---------------+-----------------+
             |               |                 |
   fato_distrito_indicador   fato_distrito_perfil    fato_prioridade_ocorrencias
          (1056)                  (96)                        (96)
         /      \                 /    \                        /
 dim_distrito  dim_indicador  dim_distrito dim_perfil          dim_distrito
     (96)           (11)          (96)        (9)                (96)
```

As três tabelas de fatos têm a mesma FK `snapshot_id` e `CD_DIST`. A dimensão `dim_perfil` usa `perfil_sk` com a versão e hash, para impedir que P01 de outra versão seja associado por engano. A dimensão `dim_indicador` usa `indicador_sk` de igual forma.

## Dimensões e fatos

| Entidade | Grão e chave candidata | Linhas esperadas |
|---|---|---:|
| `dim_snapshot` | `snapshot_id = versao_catalogo \| sha256_gold` | 1 |
| `dim_distrito` | `CD_DIST` oficial | 96 |
| `dim_perfil` | `perfil_sk = snapshot_id \| perfil_id` | 9 |
| `dim_indicador` | `indicador_sk = snapshot_id \| indicador_id` | 11 |
| `fato_distrito_indicador` | `(snapshot_id, CD_DIST, indicador_sk)` | 1056 |
| `fato_distrito_perfil` | `(snapshot_id, CD_DIST)` | 96 |
| `fato_prioridade_ocorrencias` | `(snapshot_id, CD_DIST)` | 96 |

### Fato de indicadores

- `valor_numerico` mantém a medida da Gold **sem normalização adicional**.
- `dim_indicador` especifica aliases exatos de `SOURCE_FIELDS` v2, coluna Gold original, unidade e procedência.
- Crimes são **taxas** por 100 mil habitantes, infraestrutura é **quantidade relativa** por 10 mil habitantes, densidade é habitantes/km², empregos são vínculos.
- Não somar indevidamente medidas de diferentes tipos ou dimensões. Empregos, taxas e densidade não são métricas aditivas equivalentes.
- A marca `periodo_referencia_documentado='2021'` do indicador de empregos é evidência externa à estrutura Gold wide; `periodo_validado_na_gold=False`. Os demais períodos não são inventados.

### Fato de atribuição a perfil

- Contém somente atributos calculados para classificação: `representatividade_interna_0a100`, `silhouette_individual`, `distancia_ao_centro_do_perfil`, `tipo_pertencimento`.
- **Representatividade** é posição relativa dentro do grupo, não score de aptidão residencial.
- Três linhas de fronteira devem ser preservadas.

### Fato de prioridade por ocorrências

- Uma linha por distrito com `posicao_relativa_entre_96`, percentis de roubo/furto e `indice_ordenacao_ocorrencias`.
- O ranking é **global entre os 96 distritos** e não deve ser recalculado ao filtrar um perfil.
- As taxas brutas estão no fato de indicadores, evitando fatos duplicados.

## Datas e versionamento

- `snapshot_id` identifica o **estado de dados e modelo**, não representa `data_referencia` de qualquer fonte.
- Não existe `dim_tempo` detalhada nesta prévia porque a Gold wide não possui os períodos de todas as fontes. A futura tabela física de indicadores por período dependerá da derivação contratada de anos/janelas a partir das Silvers e da definição da granularidade temporal adequada.
- Novos anos de RAIS/ObservaSampa, SSP ou GeoSampa exigem um snapshot novo e reavaliação de clusterização. Não misturar períodos sem metadados explícitos.

## Contrato para o front-end

- **Indisponível ao público**: `status=PREVIA_DIMENSIONAL_NAO_PUBLICAVEL` e `disponivel_publicamente=False`.
- Permite validar consultas e fluxo de filtros em memória, **não** representa API ou tabelas disponíveis no workspace.
- Ao exibir dados no futuro, cada cartão terá nome, explicação, unidade, fonte e ressalva. “Menos Roubos e Furtos” permanece nome candidato do P04; P07 é referenciado a 2021.

## Não escopo

- Publicação Delta, permissões de leitura, SCD2, histórico por indicador, tarefas agendadas, ingestão incremental e mecanismo Lambda.
- A arquitetura Lambda terá entrega separada, sem falsamente chamar snapshots estáticos de streaming em tempo real.
