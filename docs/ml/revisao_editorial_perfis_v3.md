# BairroIQ — Nomes orientados ao usuário: revisão de coerência (v3)

**Status:** candidatos, sem autorização de publicação. O ML e os 96 distritos não mudaram.

## Decisão de produto

- **Clustering** descreve nove tipos observados de distrito, inclusive características que podem ser desvantagens; nenhum é promessa de qualidade de vida.
- **Prioridades** são filtros/ordenações independentes dos clusters; “Menos Roubos e Furtos” é prioridade de busca nos 96 distritos e também dentro de um perfil.
- **P04**: o eixo combinado de ocorrências é abaixo da referência, mas a afirmação de *ambas* as taxas individuais menores depende de auditoria. `audit_p04` pode propor o título alternativo, nunca homologá-lo automaticamente.
- **P07**: o indicador de empregos é chamado “empregos formais no município — total”; até confirmar sua granularidade por distrito, não afirmar “polo de empregos”, “muitas oportunidades” ou vantagens trabalhistas locais. Se a fonte não for distrital, remover ou substituir o eixo e **retreinar o modelo**; mudar só o rótulo não resolverá.
- Infraestrutura de transporte por habitante não informa frequência ou tempo de viagem; praças cadastradas não garantem verde acessível; escolas/UBS por habitante não indicam vagas nem qualidade.

## Cartões propostos (não publicados)

| ID | Título claro | Texto de apoio |
|---|---|---|
| P01 | Mais Praças, Vida Urbana | Regiões com mais praças e corredores verdes cadastrados por habitante, e maior densidade de moradores. |
| P02 | Praças em Regiões Menos Densas | Mais praças e corredores verdes por habitante, com menor número de moradores por km². |
| P03 | Áreas Pouco Povoadas | Distritos com baixa concentração de moradores por km²; compare o acesso a transporte e serviços separadamente. |
| P04 | Menos Ocorrências Registradas | O índice combinado de roubos e furtos registrados é menor neste grupo; cada taxa e distrito exigem análise própria. |
| P05 | Transporte Coletivo em Destaque | Mais equipamentos de transporte coletivo por habitante, mas também mais ocorrências criminais registradas. |
| P06 | Muitos Moradores por Km² | Áreas mais adensadas, com menos escolas públicas e UBS cadastradas por habitante. |
| P07 | Empregos em Destaque | O indicador de empregos formais é elevado, mas ainda não sabemos se representa empregos localizados no distrito. |
| P08 | Mais Moradores, Menos Transporte | Alta densidade de moradores e menor número relativo de equipamentos de transporte coletivo por habitante. |
| P09 | Escolas e UBS por Habitante | Maior número relativo de escolas públicas e unidades básicas de saúde cadastradas por habitante. |

## Checklist editorial para o front-end

1. Exibir uma entrada **“O que é importante para você?”** com critérios independentes: menos registros de roubos e furtos, transporte, praças, escolas/UBS e densidade. Implementados nesta PR: **somente** a prioridade de roubos/furtos. Não prometer que os demais filtros já foram implementados.
2. Em outra área, **“Explore os tipos de região”**, mostrar os nove perfis somente **após homologação**; enquanto isso, `disponivel_publicamente=false` para todos.
3. P04 e P07 têm `pendencia_critica_editorial`; o front deve respeitar o bloqueio. O motor de preferência por crimes não modifica os clusters.
4. Ao selecionar um perfil, mostrar indicadores quantitativos, distrito a distrito, fonte, período de referência e limites da interpretação.
5. Nunca prometer “mais seguro”, “melhor para crianças”, “perto de tudo”, “transporte rápido” ou “mais empregos no bairro” sem dado específico.

## Métricas e pesquisa com usuário

Medir se as pessoas entendem cada título e conseguem distinguir P01/P02/P03 e P06/P08. A estabilidade ARI do K-Means K9 permanece moderada (mediana ~0,471) e a Silhouette geral ~0,1945; esses números precisam permanecer visíveis na metodologia, não na tela principal.
