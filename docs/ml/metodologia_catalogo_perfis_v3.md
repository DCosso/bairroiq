# BairroIQ — Catálogo candidato de nove perfis territoriais (ML v3)

**Status:** `CANDIDATO_REVISAO_SEMANTICA`. Código implementado e testado em dados sintéticos no CI; **a execução real da v3 sobre a Gold ainda precisa ser feita**. Este PR **não publica tabelas**, não homologa nomes e não altera o algoritmo exploratório v2.

## Decisão metodológica rastreável

No experimento real da v2 com **96 distritos**, o K-Means com **K=9** e *winsorização do eixo densidade (log1p) entre P10 e P90* produziu os indicadores observados abaixo:

| Medida | K-Means K9 P10–P90 | K-Means K10 P05–P95 | Ward K8 P05–P95 |
|---|---:|---:|---:|
| Silhouette (maior melhor) | 0,194467 | 0,169554 | 0,193960 |
| Davies-Bouldin (menor melhor) | 1,334164 | 1,313386 | 1,202354 |
| Estabilidade ARI mediana (40 subamostras 80%) | 0,470918 | 0,400553 | 0,629504 |
| Silhouette individual negativo | 3/96 (3,125%) | 13/96 (13,54%) | 10/96 (10,42%) |
| Menor / maior grupo | 6 / 22 | 4 / 15 | 4 / 23 |

**Escolha de produto, não superioridade científica universal:** K9 tem nove perfis, mais perto da meta de dez; somente três classificações com Silhouette negativo e todos os grupos possuem 6 a 22 distritos. O Ward K8 é mais estável na amostragem e tem Davies-Bouldin menor. A estabilidade K9 é moderada, e a separação global é baixa: nenhuma métrica mede segurança, qualidade de vida, satisfação de usuário ou acurácia sem *ground truth*.

## Fonte e reprodução estrita

- Tabela: `workspace.gold.distritos_wide`.
- Hash completo de entrada: `726091fefefa868fd5d0d2c6929b1d68c4849941f4c7510b4fee0d93a075d38b`.
- Modelo de código: `barrioiq_pipeline/ml_perfis_territoriais_v2.py` (K-Means: `n_init=20`, `random_state=42`, `max_iter=500`).
- Seis eixos: atividade formal (granularidade pendente), roubos e furtos registrados, modais por habitante, praças e corredores verdes cadastrados, escolas e UBS por habitante, densidade populacional.
- A transformação de densidade é aplicada **ao eixo log1p ANTES da padronização final**, com P10/P90 aprendidos a partir dos 96 distritos. Os dados brutos da Gold não são modificados.
- `catalogo_perfis_v3_config.json` contém os nove nomes editoriais, as direções dos eixos que os sustentam e **os 96 `CD_DIST` únicos** distribuídos por perfil, conforme a auditoria do K9 original.
- `ml_catalogo_perfis_v3.py` falha **antes de entregar dados ao front** quando divergem o hash, a composição de qualquer perfil, a direção de seus eixos, a contagem de Silhouettes negativos, as métricas ou os guardrails operacionais. Alterações legítimas exigem nova revisão/versionamento.

## Escolha de perfis pelo usuário

Um perfil é uma **opção descritiva de comparação territorial**, não um filtro de preferências individual aprendido pelo modelo. A interface deverá oferecer nove opções sem ranking de bom/ruim. Ao selecionar uma opção, mostrar os distritos que a compõem, os três exemplos mais centrais no espaço das features e os contrastes de indicadores em relação ao conjunto dos 96 distritos.

Os nomes estão escritos para o usuário final, com títulos curtos e linguagem de produto, e continuam **provisórios**, especialmente P4 e P7, que usam o indicador ObservaSampa denominado “empregos formais no município — total” sem sua granularidade territorial ainda validada. Nenhum perfil significa “seguro”, “barato”, “melhor para família”, “rápido deslocamento”, “arborizado” ou “boa oferta local de vagas”; estes desfechos não foram medidos pela modelagem.

| Perfil | Nome editorial provisório | Distritos | Eixos definidores |
|---|---|---:|---|
| P01 | Mais Praças, Vida Urbana | 9 | verde/lazer ↑, densidade ↑ |
| P02 | Praças em Regiões Menos Densas | 7 | densidade ↓, verde/lazer ↑ |
| P03 | Áreas Pouco Povoadas | 6 | densidade ↓, atividade ↓ |
| P04 | Menos Ocorrências Registradas | 22 | atividade ↓, ocorrências ↓ |
| P05 | Transporte Coletivo em Destaque | 7 | mobilidade ↑, ocorrências ↑ |
| P06 | Muitos Moradores por Km² | 8 | serviços públicos ↓, densidade ↑ |
| P07 | Empregos em Destaque | 12 | atividade ↑, serviços públicos ↓ |
| P08 | Mais Moradores, Menos Transporte | 19 | densidade ↑, mobilidade ↓ |
| P09 | Escolas e UBS por Habitante | 6 | serviços públicos ↑, densidade ↓ |

**Casos auditados de fronteira:** Mooca (P02; Silhouette −0,073790), Socorro (P02; −0,047286) e Lajeado (P08; −0,0057 aprox.). Eles permanecem no perfil atribuído pelo algoritmo, não são movidos manualmente. Mais informação no relatório de auditoria da execução K9.

## Representatividade dentro de cada perfil

A v3 usa a distância euclidiana do distrito para o **centro do próprio cluster no espaço padronizado**. Dentro de cada grupo, calcula um percentil ordinal de proximidade (100 para o mais próximo, 0 para o mais afastado). Esse valor **não deve ser usado como pontuação de qualidade de vida, segurança, preço ou recomendação personalizada**, nem comparado entre grupos diferentes. O resultado também traz Silhouette individual e `tipo_pertencimento` (`FRONTEIRA` se Silhouette negativo).

## Governança e homologação

Esta etapa usa `publicacao_gold_autorizada=false` de propósito. Requer: (1) executar v3 no Databricks e comparar hash e perfis; (2) revisão editorial dos nomes e explicações; (3) auditar a granularidade de empregos; (4) validar a experiência com o colega do front-end e o contrato dos dados; (5) aprovação explícita da publicação. Só então criar a Gold distinta da Gold wide e definir o esquema dimensional e o plano Lambda. O CI usa dados sintéticos exclusivamente para testar funcionamento e segurança, nunca para afirmar resultados sobre São Paulo.

## Regra editorial para os cartões do usuário

O título do cartão é `nome_provisorio`; a linha de apoio é `interesse_usuario`. Para detalhes, exibir `descricao_provisoria`, indicadores e `ressalva_especifica`. A clareza comercial não autoriza prometer segurança, silêncio, preço baixo, proximidade a pé, qualidade de serviços, arborização ou oportunidades locais de trabalho. Perfis P04 e P07 não devem ser divulgados como afirmação sobre economia local sem validar a granularidade do indicador de empregos.

| Perfil | Título ao usuário | Texto de apoio |
|---|---|---|
| P01 | Mais Praças, Vida Urbana | Explore regiões mais adensadas com maior oferta relativa de praças e corredores verdes cadastrados. |
| P02 | Praças em Regiões Menos Densas | Explore distritos menos adensados com mais praças cadastradas por habitante. |
| P03 | Áreas Pouco Povoadas | Compare distritos com menos moradores por quilômetro quadrado. |
| P04 | Menos Ocorrências Registradas | Compare distritos com valores relativamente menores nos indicadores de atividade formal e ocorrências registradas. |
| P05 | Transporte Coletivo em Destaque | Explore regiões em que os equipamentos de transporte coletivo se destacam nos dados por habitante. |
| P06 | Muitos Moradores por Km² | Compare regiões de maior densidade, observando também a oferta relativa de escolas e UBS. |
| P07 | Empregos em Destaque | Explore distritos com valores relativamente elevados no indicador de empregos formais, ainda sob auditoria de granularidade. |
| P08 | Mais Moradores, Menos Transporte | Compare regiões mais adensadas com menor quantidade relativa de equipamentos de transporte coletivo. |
| P09 | Escolas e UBS por Habitante | Explore distritos com mais escolas públicas e UBS cadastradas por habitante. |

## Checagem editorial de ocorrências

O P04 possui o nome alternativo candidato "Menos Roubos e Furtos". Não inferir "mais seguro" a partir da média z-score do eixo `ocorrencias`. A nova auditoria exige separadamente: mediana do P04 inferior à mediana dos 96 distritos em **roubos e furtos**; 60% dos membros do P04 abaixo de ambas as referências. A aprovação do nome permanece humana e este limiar é editorial, não estatístico. A ordenação por prioridade é independente da clusterização. Ver `docs/ml/contrato_preferencia_ocorrencias_v1.md`.
