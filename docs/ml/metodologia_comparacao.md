# BairroIQ — Experimento comparativo de clusterização territorial

**Problema:** caracterizar perfis socio-urbanos dos 96 distritos administrativos de São Paulo, sem chamar as classes de "melhores" ou "piores". **Estado:** exploração reproduzível com dados reais exportados da Gold; **nenhum cluster homologado em produção**.

## 1. Objetivo de produto versus escolha científica

A interface pretende exibir **aproximadamente dez perfis**; `k=10` é uma preferência de granularidade do produto, e **não uma quantidade comprovada de grupos naturais**. Por isso, o experimento registra simultaneamente:

- **Cenário exploratório:** avaliar `k=2..12`, selecionar o maior Silhouette entre opções com pelo menos 5 distritos por grupo (critério operacional exploratório).
- **Cenário de produto:** comparar K-Means e Ward com `k=10` fixo, **mesmo quando não atende ao critério de tamanho**, e explicitar todos os grupos pequenos.

Não selecionar um modelo só pelo Silhouette: considerar distribuição dos grupos, estabilidade sob subamostragem, sensibilidade às variáveis, interpretação e futura utilidade da interface. **Nunca renomear IDs de cluster como notas ou ranking.**

## 2. Dados e pré-processamento

- **Fonte:** `workspace.gold.distritos_wide` (96 linhas, 254 campos). `CD_DIST` identifica cada observação; latitude/longitude e nome são dados de saída, não entram no ajuste.
- **Variáveis originais (6):** empregos formais (`obs_empregos_formais_no_municipio_total_86858d5b`), roubos por 100 mil habitantes, corredores verdes por 10 mil habitantes, metrô/ônibus/trem por 10 mil habitantes. Nomes exatos no script `ml_distritos_comparacao.py`.
- **Dimensões de treino (4):** log1p de empregos, log1p de roubos, corredores verdes, e média de três z-scores de transporte. Padronização z-score final de cada dimensão, com mesma importância inicial para distância euclidiana.
- **Contrato de entrada:** exatamente 96 `CD_DIST` únicos e não nulos, seis indicadores finitos não negativos, coordenadas válidas e nomes presentes. Falhas interrompem o experimento, sem imputação silenciosa.
- **Referência de nomes:** `distritos_centroides_ibge_2022.json`, associada por `CD_DIST`; nenhum nome é inferido por similaridade.
- **Sem leakage por ID:** nomes, códigos e coordenadas não fazem parte das features; o ajuste não é temporal.

**Atenção à semântica:** "empregos formais no município - total" precisa de verificação de granularidade/ano na fonte ObservaSampa antes de ser apresentado como oferta de empregos local; corredores verdes não medem arborização; taxa de roubos não é probabilidade individual de vitimização; infraestrutura de transporte por habitantes não mede tempo de deslocamento. Preços imobiliários não entraram no treino devido à cobertura territorial parcial (39,72% de estoque homologado na última verificação).

## 3. Métodos concorrentes

| Propriedade | K-Means | Aglomerativo (Ward) |
|---|---|---|
| Família | Particional, centróides iterativos | Hierárquico, fusões sucessivas |
| Parâmetros | `random_state=42`, `n_init=20`, `max_iter=500` | `linkage=ward`, corte em `k` grupos |
| Vantagem operacional | Pode atribuir nova observação com modelo e scaler persistidos | Visualização hierárquica/dendrograma |
| Limitações | Sensível a escala, outliers e número de centros | Sensível a escala, outliers e corte hierárquico; sem `predict` padrão |
| Viés comum | Distância euclidiana e favorecimento de grupos compactos | Distância euclidiana e favorecimento de grupos compactos |

Embora sejam dois algoritmos distintos, não representam abordagens totalmente independentes (ao contrário de um método baseado em densidade). São comparados em igualdade de features e transformações.

**Métricas:** Silhouette (maior), Davies-Bouldin (menor), Calinski-Harabasz (maior), tamanhos de clusters, ARI entre algoritmos, ARI por 100 subamostras sem reposição de 80% dos distritos e ARI retirando cada dimensão (*ablation*). ARI é invariável à permutação dos IDs. **Não existe ground truth:** nenhuma métrica é "acurácia".

## 4. Resultados reproduzidos do CSV exportado do Databricks

Os valores abaixo foram produzidos pelo código versionado sobre `distritos_classificados.csv`, com origem `CSV_EXPORTADO_DO_DATABRICKS`. Confirmar o SHA e reproduzir diretamente da Gold antes de publicação física.

| Modelo | Cenário | K | Silhouette | Davies-Bouldin | Calinski-Harabasz | Menor grupo | Maior grupo |
|---|---|---:|---:|---:|---:|---:|---:|
| K-Means | Exploratório | 3 | 0,426276 | 0,973417 | 47,816765 | 7 | 67 |
| Ward | Exploratório | 3 | 0,486909 | 0,795872 | 40,451523 | 5 | 81 |
| K-Means | **Produto** | **10** | **0,258470** | **0,910293** | 42,646920 | **1** | 29 |
| Ward | **Produto** | **10** | 0,249642 | 0,970229 | 40,610295 | **1** | 27 |

Distribuição de K=10 (ordenada, sem associar a ID de cluster):

- **K-Means:** `1, 2, 2, 2, 4, 7, 7, 19, 23, 29` — quatro grupos de até 2 distritos.
- **Ward:** `1, 2, 2, 5, 7, 8, 10, 11, 23, 27` — três grupos de até 2 distritos.

**Conclusão:** é possível calcular 10 grupos, porém o resultado atual mostra segmentação excessiva para algumas observações. O produto pode usar a previsão de "aproximadamente dez perfis" como requisito de experiência, **mas não deve publicar esses 10 grupos como clusters estáveis já homologados**.

### Estabilidade e sensibilidade, K=10

| Indicador | K-Means | Ward |
|---|---:|---:|
| ARI mediana em 100 subamostras de 80% | 0,695351 | 0,632184 |
| ARI sem empregos | 0,388334 | 0,491049 |
| ARI sem roubos | 0,599617 | 0,569503 |
| ARI sem corredores verdes | 0,554994 | 0,328636 |
| ARI sem mobilidade | 0,742916 | 0,390155 |

ARI de concordância entre K-Means e Ward com K=10: **0,398697**. Não significa concordância plena; semelhança parcial entre partições é esperada.

O melhor índice varia conforme métrica e objetivo. **K-Means é candidato operacional** pela facilidade de inferência e maior estabilidade por subamostra neste experimento, mas a decisão deve ser formalizada **após** revisão semântica das variáveis e tratamento justificado de clusters muito pequenos, sem alterar arbitrariamente o algoritmo apenas para atingir uma meta visual.

## 5. Artefatos e rastreabilidade

- `barrioiq_pipeline/ml_distritos_comparacao.py`: código reproduzível, com validação de entrada, features, dois algoritmos, K=2..12, cenários exploratório e K=10, avaliação e exportação.
- `tests/test_ml_distritos_comparacao.py`: testes de contrato, preparação, reprodutibilidade e exportação dos dois cenários.
- `docs/ml/metricas_modelos.csv`: **22 experimentos** (2 algoritmos × 11 valores de K) com métricas e tamanhos.
- `docs/ml/distritos_clusters_comparados.csv`: rótulos exploratórios e K=10 para os 96 distritos; **não usar como classificação homologada**.
- `docs/ml/perfis_clusters.csv`: resumos por cluster dos dois cenários.
- `docs/ml/resumo_experimento.json`: versões, hashes, métricas, sensibilidade e status de homologação.
- `docs/arquitetura/star_schema_lambda.md`: plano de modelagem OLAP e arquitetura Lambda, com status dos componentes.

Para reproduzir localmente, instalar `barrioiq_pipeline/requirements-ml.txt` e executar:

```bash
python barrioiq_pipeline/ml_distritos_comparacao.py \
  --csv distritos_classificados.csv \
  --output-dir resultados/ml_distritos
python -m unittest discover -s tests \
  -p 'test_ml_distritos_comparacao.py' -v
```

No Databricks: importar `run_from_spark(spark)` do módulo versionado; validar correspondência dos dados/versões e exportações antes de qualquer publicação. A publicação de Gold e os contratos consumíveis pelo front-end exigem etapa separada de aprovação.
