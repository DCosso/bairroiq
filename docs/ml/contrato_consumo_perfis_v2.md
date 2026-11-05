# BairroIQ — Contrato exploratório de perfis para o front-end

**Status:** `EXPLORATORIO_NAO_HOMOLOGADO`; saídas CSV/JSON, **não** tabelas Gold. Nenhum número sintético deve ser exibido como real.

## Escolha do usuário

A interface apresenta uma **lista de perfis territoriais**, sem ordenar do “melhor” ao “pior”. Ao selecionar um perfil, mostra os distritos classificados e as evidências. O usuário pode voltar, trocar de perfil e comparar opções. Esta experiência descreve **similaridade estatística**, não uma recomendação pessoal garantida.

## Dataset de perfis (`perfis_v2.csv`)

- `perfil_id`: identificador único do perfil no cenário, p. ex. `kmeans-k09-p03` (formato, não resultado real).
- `metodo`: `kmeans` ou `ward`.
- `k`: 8, 9 ou 10; sempre exibido no contexto dos resultados.
- `cluster_id`: número estável **apenas dentro do mesmo método, K e versão**; não é nota de qualidade.
- `perfil_nome_provisorio`, `perfil_descricao_provisoria`: explicações automáticas sujeitas a revisão humana.
- `qtd_distritos`: quantidade de distritos integrantes.
- `evidencias_json`: principais eixos, respectivas medianas z-score e direção relativa.
- `alertas_json`: avisos para grupos singulares e rótulos não homologados.
- `mediana_<variavel>`: medianas de 11 indicadores originais do cluster.
- `modelo_versao`, `status`: controle de publicação.

## Dataset de distritos (`distritos_perfis_v2.csv`)

- `CD_DIST` (**chave territorial**), `NM_DIST`, `latitude`, `longitude` (centróides IBGE, não endereços).
- `metodo`, `k`, `cluster_id`, `perfil_id`, `perfil_nome_provisorio`, `modelo_versao`, `status`.
- Uma linha por distrito **para cada** combinação método/K. Com dois métodos e três valores de K, esperamos `96 x 2 x 3 = 576` linhas; uma versão homologada filtrará **um único cenário** para uso efetivo.
- A UI **não deve misturar perfis de algoritmos ou K diferentes** na mesma seleção.

## Dataset de métricas (`metricas_v2.csv`)

- Uma linha por (algoritmo,K): 22 combinações, com Silhouette, Davies-Bouldin, Calinski-Harabasz, concentração, grupos unitários, grupos de até 2 distritos, Silhouette individual negativa e elegibilidade operacional.

## Homologação posterior

Quando aprovado, uma Gold de consumo distinta da Gold wide poderá materializar duas entidades: catálogo de perfis (dimensão) e atribuição perfil ↔ distrito (ponte/fato sem medidas), sempre com `modelo_versao` e `validade`. A interface só receberá registros `HOMOLOGADO`, e seus indicadores reais serão fornecidos pela camada de consumo. **Não publicar diretamente as saídas exploratórias.**

Não representar `corredores_verdes` como arborização; não representar estoque imobiliário como preço de aluguel; não usar nomes de bairro como se fossem os 96 distritos oficiais.
