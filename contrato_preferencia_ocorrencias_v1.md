# BairroIQ | Prioridade de busca: menos roubos e furtos (experimental)

## Objetivo para o usuário

**Cartão / preferência:** "Menos roubos e furtos".
**Texto de apoio:** "Compare distritos com menores taxas de roubos e furtos registrados por 100 mil habitantes."
**Ressalva sempre visível:** ocorrências registradas não garantem segurança e não representam outros tipos de crime, subnotificação ou risco futuro.

A prioridade funciona **sem selecionar perfil** (nos 96 distritos) e **após selecionar um dos nove perfis**. A escolha de um perfil NÃO muda a classificação K-Means; só filtra os candidatos já classificados. Priorizar segurança NÃO é um décimo cluster, nem implica recalcular K-Means.

## Origem de dados e método

Fonte única, auditada: `workspace.gold.distritos_wide`. Colunas originais:

- `ssp_registros_12m_roubo_art_157_41b94022_por_100mil_hab`
- `ssp_registros_12m_furto_art_155_2c3ca8b1_por_100mil_hab`

Cada distrito recebe percentis calculados sobre os **96 distritos**, com valores menores sendo apresentados primeiro. O índice exclusivamente técnico de ordenação é **50% percentil da taxa de roubo + 50% percentil da taxa de furto** (sem pesos subjetivos). Empates: menor pior percentil; depois `CD_DIST`. As taxas por 100 mil são fornecidas junto com a ordenação. Não usar `indice_ordenacao_ocorrencias` nem a posição como "nota de segurança" ou probabilidade de vitimização.

Importante: a média de taxas distritais **não** é a taxa agregada da cidade. O algoritmo usa a mediana das taxas de cada um dos 96 distritos somente para comparação relativa; não declara uma taxa municipal agregada.

## Contrato de saída

`distritos_prioridade_ocorrencias.csv` (96 linhas): `CD_DIST`, `NM_DIST`, `perfil_id`, `cluster_id`, `roubos`, `furtos`, `percentil_relativo_roubos_0a100`, `percentil_relativo_furtos_0a100`, `indice_ordenacao_ocorrencias`, `posicao_relativa_entre_96`, `prioridade_id`, `status_prioridade`, e atributos do catálogo v3. A interface pode filtrar por `perfil_id` preservando a posição global de comparação. O campo `representatividade_interna_0a100` mede proximidade ao centro do cluster; não é qualidade de vida.

`catalogo_com_prioridade_ocorrencias.csv` (9 linhas): catálogo v3 com `nome_exibicao_proposto`, `nome_validado_para_publicacao=False`, ressalvas. O nome da opção P04 só vira **candidato** "Menos Roubos e Furtos" se ambas as medianas das taxas de roubos e furtos de P04 estiverem abaixo das medianas dos 96 distritos **e** pelo menos 60% dos distritos P04 estiverem abaixo das duas medianas. Caso contrário, mantém o nome vigente. 60% é guardrail editorial provisório, não critério científico universal; decisão final depende de inspeção humana dos dados e cobertura temporal.

`auditoria_nome_p04.json`: medianas do conjunto de 96 distritos e do P04, quantidade e fração de distritos com ambas as taxas abaixo, `condicao_editorial_atendida` e `nome_homologado=False`.

`resumo_prioridade_ocorrencias.json`: hash da Gold, fonte, versão do catálogo, critério comparativo, status e bloqueio de publicação.

## Limites do produto / QA

- Mostrar dados e datas de referência (janela `12m` é indicada no campo, mas período final depende de metadados de atualização da Gold).
- Ocorrências são registros administrativos, com potencial subnotificação, padrões de circulação, vieses de denúncia e efeitos do denominador populacional.
- Não atribuir "seguro", "perigoso", "sem criminalidade", "chance de assalto", ou "risco individual" a um distrito.
- Não inferir risco individual a partir de uma etiqueta de perfil; mesmo perfis com menor mediana podem conter distritos com taxas elevadas.
- Nenhuma tabela Gold pode ser escrita; `publicacao_gold_autorizada=False` e `status=EXPLORATORIO_NAO_HOMOLOGADO`.
- Se hash ou composição do K-Means v3 mudar, o processo interrompe com erro e requer nova auditoria.
- Segurança no produto é **preferência de ordenação**, não classificação nova nem probabilidade.
