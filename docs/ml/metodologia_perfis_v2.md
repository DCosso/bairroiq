# BairroIQ — Perfis territoriais v2: metodologia e decisão científica

**Status:** experimento implementado em código; **não executado ainda sobre a Gold do Databricks**. Nenhuma tabela foi criada ou modificada. **Experimento v1 preservado** para comparação histórica.

## Problema de negócio

O usuário do BairroIQ deve escolher um **perfil territorial que corresponda a suas prioridades** (p. ex., maior presença relativa de transporte, equipamentos públicos ou áreas de lazer). O sistema mostra os distritos pertencentes ao perfil e uma justificativa observável. Perfis **não são rankings** nem representam causalidade, segurança individual ou qualidade de vida absoluta. O front-end é responsabilidade de outro integrante; a Engenharia de Dados prepara os contratos.

## Dados e granularidade

Fonte: `workspace.gold.distritos_wide` (96 distritos oficiais, chave `CD_DIST`). Usa 11 colunas de entrada do dicionário homologado; latitude, longitude e nome somente para apresentação. Código completo em `barrioiq_pipeline/ml_perfis_territoriais_v2.py` (`SOURCE_FIELDS`). O código consulta a Gold diretamente, converte para pandas, valida 96 distritos, unicidade, ausência de nulos, valores não negativos e coordenadas plausíveis. Os nomes são normalizados pela referência IBGE 2022 versionada e associados por `CD_DIST`.

**O teste `teste_features.csv` cobre os seis novos indicadores:** 96/96 valores preenchidos; são estatísticas agregadas, **insuficientes para calcular clusters v2**, que dependem dos valores de cada um dos 96 distritos. Os clusters v2 só serão conhecidos após executar `run_from_spark(spark)`.

## Engenharia de atributos — seis eixos interpretáveis

| Eixo | Indicadores de entrada | Transformação |
|---|---|---|
| Atividade econômica | Empregos formais (indicador ObservaSampa) | `log1p` |
| Ocorrências criminais | Roubo e furto por 100 mil hab. | `log1p` + padronização individual + média |
| Mobilidade | Metrô, ônibus e trem por 10 mil hab. | `log1p` + padronização individual + média |
| Áreas verdes e lazer | Praças/largos e corredores verdes por 10 mil hab. | `log1p` + padronização individual + média |
| Serviços públicos | Escolas públicas e UBS por 10 mil hab. | `log1p` + padronização individual + média |
| Densidade populacional | Habitantes por km² | `log1p` |

No final, os seis eixos são padronizados por `StandardScaler`, **sem dar peso triplo** à mobilidade ou às ocorrências criminais. A iluminação LED fica fora do ajuste pela distribuição quase saturada (mediana de 100%), mas pode permanecer como dado de exibição. A padronização é recalculada dentro de cada subamostra; nomes, coordenadas, IDs e preços imobiliários não entram no treino.

**Limitações:** indicador de empregos chamado “no município” exige auditoria do significado territorial; praças/corredores verdes **não medem arborização**; taxas registradas de crimes não representam risco individual; equipamentos por habitante não medem distância, frequência ou qualidade de serviço; o custo de vida não foi modelado devido à incompletude territorial imobiliária. Por isso, os rótulos de atividade econômica são especialmente provisórios.

## Comparação e escolha de K

- Mesmos seis eixos e mesmos registros para **K-Means** (`n_init=20`, `random_state=42`) e **Ward hierárquico** (`linkage='ward'`). Ambos favorecem geometrias euclidianas compactas e não são métodos radicalmente independentes.
- Exploração de `K=2..12` para ambos, sem forçar 10 e sem afirmar que 10 grupos naturais existem.
- Produção de fichas de perfil provisórias para `K=8, 9, 10`, de ambos os algoritmos, independentemente de sua elegibilidade. O requisito de experiência é **aproximadamente 10 opções**.
- Guardrail operacional provisório: cada grupo >=3 distritos, maior grupo <=50% da amostra. **Não é uma lei estatística** e pode ser revisado com justificativa, especialmente para outliers verdadeiros.
- Primeiro candidato de cada algoritmo = **K mais próximo de 10** dentre cenários que satisfazem o guardrail. Isso **não homologa** nem determina automaticamente o algoritmo vencedor.
- Critérios de defesa: Silhouette (maior), Davies-Bouldin (menor), Calinski-Harabasz (maior), percentual com Silhouette individual negativo, concentração, tamanhos, ARI de estabilidade (40 amostragens de 80%) e ARI quando um eixo é retirado.
- Não há rótulos verdadeiros. **Nenhuma métrica é “acurácia”.** O valor de Silhouette não mede satisfação dos usuários.

## Como gerar nomes e explicações

Para cada cluster, calcular **medianas dos eixos padronizados** (em unidades z-score), ordenar pelo valor absoluto e destacar uma ou duas dimensões mais distintivas. Nomes são gerados de forma **determinística, provisória e descritiva**, por exemplo “Mais equipamentos de transporte por habitante / Menos ocorrências registradas” **somente se os dados do cluster indicarem isso**. Esses exemplos não são resultados já obtidos.

A ficha exportada contém `perfil_id`, nome, descrição, quantidade de distritos, evidências em JSON (eixo, mediana z-score e sentido), alertas e mediana de cada variável original. Nomes não podem prometer morar barato, ser seguro, “tranquilidade”, investimentos rentáveis ou acesso próximo quando isso não for efetivamente medido. Antes de publicação é obrigatório: revisão semântica da origem, avaliação de grupos singulares, análise por distrito, nomeação humana e aprovação do contrato do front-end.

**Exemplo de interpretação correta:** “O cluster apresenta taxas registradas de roubos e furtos relativamente menores entre os 96 distritos”. **Incorreto:** “É seguro morar aqui”.

## Rastreabilidade e entregas

- `barrioiq_pipeline/ml_perfis_territoriais_v2.py`: leitura, feature engineering, K-Means, Ward, métricas, estabilidade, sensibilidade, explicações e exportação CSV/JSON.
- `tests/test_ml_perfis_territoriais_v2.py`: 18 testes unitários com dados **sintéticos apenas para teste**, não usados nas conclusões.
- `.github/workflows/ml-v2-ci.yml`: CI dedicado, dependências fixadas, sem escrita de tabelas.
- `docs/ml/contrato_consumo_perfis_v2.md`: tabela de consumo para escolha de perfil.
- `docs/ml/execucao_databricks_perfis_v2.md`: execução na Gold e exportação opcional de artefatos locais.
- `docs/ml/metodologia_comparacao.md` e `ml_distritos_comparacao.py`: **baseline v1 preservado**.

**Decisão pendente:** não declarar vencedor, valores de Silhouette v2, número final de perfis nem nome definitivo sem os resultados reais da Gold v2. Publicação Gold só em etapa posterior com contratos, testes e aprovação.
