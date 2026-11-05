# BairroIQ — Contrato v3 de perfis selecionáveis (candidato)

**Não disponibilizar em produção ainda:** `status=CANDIDATO_REVISAO_SEMANTICA` e `publicacao_gold_autorizada=false`. A v3 gera artefatos pandas/CSV/JSON locais; não altera Gold nem publica API.

## Entidade `catalogo_perfis_v3.csv` — nove linhas

| Coluna | Uso no frontend |
|---|---|
| `perfil_id` | ID como `kmeans-k09-p05` (estável só na versão/snapshot atual) |
| `cluster_id` | Número 1 a 9, sem ordem de qualidade |
| `nome_provisorio` | Texto da opção selecionável, sujeito à revisão |
| `descricao_provisoria` | Descrição relativa aos indicadores medidos |
| `interesse_usuario` | Orientação descritiva, sem promessa de adequação pessoal |
| `ressalva_especifica` | Limitações pertinentes ao grupo |
| `qtd_distritos` | Número de distritos integrantes |
| `exemplos_distritos_json` | Três membros mais próximos do centro do seu grupo |
| `evidencias_json` | Três eixos dominantes, `mediana_z` e `direcao` |
| `medianas_originais_json` | Medianas dos 11 campos de origem, para auditoria |
| `silhouette_mediana` | Evidência técnica de coerência, não pontuação do perfil |
| `distritos_silhouette_negativa` | Quantidade de pontos de fronteira |
| `metodo`, `k`, `catalogo_versao`, `sha256_gold`, `status` | Metadados e governança |
| `publicacao_gold_autorizada` | Sempre `false` neste pacote |

## Entidade `distritos_por_perfil_v3.csv` — 96 linhas

Uma linha por **distrito oficial** (identificador `CD_DIST`, único), contendo `NM_DIST`, latitude, longitude do centroide IBGE, `perfil_id`, `cluster_id`, nome provisório, distância ao centro, Silhouette individual, `tipo_pertencimento`, representatividade relativa interna, versão/hash/status.

**`representatividade_interna_0a100`:** valor ordinal comparável somente entre distritos **dentro do mesmo perfil**; 100 indica o distrito estatisticamente mais próximo do centro desse grupo. Não é ranking geral de bairros, nem chance de o usuário gostar do local. Os três casos de Silhouette negativo recebem `tipo_pertencimento=FRONTEIRA` para revisão.

## Comportamento recomendado do produto (após homologação)

1. Exibir nove cartões de perfis com seus nomes e descrições; não ordená-los do “melhor” ao “pior”.
2. Ao escolher um perfil, listar **apenas** distritos com aquele `perfil_id` no mesmo `catalogo_versao` e `sha256_gold`.
3. Destacar evidências, limitações e casos de fronteira, sem ocultá-los.
4. Permitir trocar/comparar perfis. Preferências pessoais (tempo de trajeto, preço, segurança) exigem dados e lógica específicos e **não** podem ser inferidas dos clusters.
5. Diferenciar claramente *distritos oficiais* de bairros imobiliários não homologados.

## Proposta posterior de Star Schema (ainda não implementado)

- `dim_perfil_territorial`: uma linha por perfil e versão, com nome, descrição e contexto estatístico.
- `dim_distrito`: chave territorial estável `CD_DIST`, nome oficial, coordenadas e metadados.
- `bridge_distrito_perfil`: pares (`CD_DIST`, `perfil_id`, `modelo_versao`), com versões/validade para evitar misturar cenários.
- `fato_indicadores_distrito_periodo`: métricas por distrito/fonte/período, de granularidade contratada; **não reutilizar o hash como data do indicador**.

A publicação física, testes Delta, datas de vigência e lineage fazem parte da próxima PR de Gold/Star Schema, não desta.

## Microcopy para os cartões

Utilizar `nome_provisorio` como título de destaque (curto, linguagem simples) e `interesse_usuario` como texto de apoio, sem expor jargões como K-Means, winsorização e desvio-padrão na tela de seleção. No detalhe, manter os dados e as ressalvas auditáveis. Perfis similares no título precisam ser distinguidos pelo texto de apoio; sobretudo P01/P02/P03 e P06/P08. Títulos são rótulos editoriais, não uma preferência pessoal já validada.

## Prioridade adicional de roubos e furtos

O arquivo `prioridade_roubos_furtos_v1.py` monta os 96 distritos com ordenação separada por taxas de roubos e furtos, preservando os nove clusters. Ver `docs/ml/contrato_preferencia_ocorrencias_v1.md`. A revisão do título P04 é **condicional**, não homologação automática.

## Bloqueio editorial e separação entre perfis e prioridades

Os campos `disponivel_publicamente` e `pendencia_critica_editorial` integram o catálogo exportado.
O primeiro é `false` para todos os perfis nesta versão. O segundo explicita, especialmente para
P04 e P07, as auditorias necessárias. Não exibir cartões publicamente com `false`.
As prioridades pessoais são uma navegação separada dos clusters; no pacote atual apenas
“Menos Roubos e Furtos” possui ordenação implementada e exploratória.

Consultar `docs/ml/revisao_editorial_perfis_v3.md` para títulos e textos de apoio.
