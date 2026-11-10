# Análise Exploratória de Dados

A análise exploratória de dados (EDA) tem como objetivo compreender a estrutura, a qualidade e as principais características das bases utilizadas no projeto BairroIQ. Nesta etapa, foram realizadas análises e visualizações para identificar padrões, distribuições, possíveis inconsistências e valores ausentes, além de observar diferenças entre as regiões e as variáveis analisadas. 

Essa exploração inicial é fundamental para orientar o tratamento e a preparação dos dados, garantindo maior consistência nas etapas seguintes. Os resultados obtidos também ajudam a identificar quais indicadores são mais relevantes para o projeto, que busca integrar informações urbanas e socioeconômicas para apoiar a comparação entre bairros da cidade de São Paulo e contribuir para decisões mais informadas sobre onde morar ou trabalhar.

# Base 1 — Dados de segurança pública – SSP 

Arquivos disponíveis (6)

Shape: 10,211 linhas x 33 colunas - CelularesSubtraidos_2026.xlsx - 61.7 MB

Shape: 10,211 linhas x 33 colunas - DadosProdutividade_2026.xlsx - 110.5 MB

Shape: 10,211 linhas x 33 colunas - MDIP_2026.xlsx - 2.0 MB

Shape: 10,211 linhas x 33 colunas - ObjetosSubtraidos_2026.xlsx - 288.4 MB

Shape: 10,211 linhas x 33 colunas - SPDadosCriminais_2026.xlsx - 120.4 MB

Shape: 10,211 linhas x 33 colunas - VeiculosSubtraidos_2026.xlsx - 37.8 MB

A análise da distribuição dos registros por bairro permitiu identificar as regiões com maior concentração de ocorrências. 
Essa visualização contribui para compreender como os registros estão distribuídos geograficamente pelo município de São Paulo e identificar diferenças entre os bairros, fornecendo uma visão inicial da distribuição territorial das ocorrências. 

<img width="1187" height="787" alt="image" src="https://github.com/user-attachments/assets/df349ec3-2acc-43aa-9d85-cd21801f3145" />

# Base 2 — Observa Sampa

Shape: 206.198 linhas e 4 colunas.

Tipos de Dados: Nome (texto), Região (texto), Período (inteiro) e Resultado (texto).

Amostra das 5 primeiras linhas:

<img width="853" height="132" alt="image" src="https://github.com/user-attachments/assets/29eec9ac-aa74-43ca-8035-833b28c2714e" />

A base tem uma estrutura temporal longa para os distritos. Para a amostra visual, filtrei o indicador "Quantidade de famílias em situação de extrema pobreza" focando no distrito de Água Rasa. É possível observar o pico acentuado ocorrido ao redor de 2023.

<img width="1600" height="800" alt="image" src="https://github.com/user-attachments/assets/f73fdb72-9b75-4de0-b760-d29f1897df0f" />


# Base 3 — Guru dos imoveis

Shape: 29.612 linhas e 9 colunas.

Tipos de Dados: mes, bairro e transacao (texto); mediana_m2, p25_m2, p75_m2 e dias_no_mercado_medio (decimal); anuncios_ativos_media_dia e novos_anuncios (inteiro).

Amostra das 5 primeiras linhas:

<img width="894" height="131" alt="image" src="https://github.com/user-attachments/assets/341ede1b-0703-40f5-8103-8a4dec13c20e" />

Top Bairros por Preço (m²)
Filtrando apenas as transações de "venda" na base do Guru dos Imóveis, o gráfico Top 10 bairros com a maior mediana do metro quadrado 
(nota: os valores brutos mostram alguns recortes fora da curva como "Não Informado" ou bairros rurais isolados).

<img width="1600" height="800" alt="image" src="https://github.com/user-attachments/assets/27bc90d2-0dcb-4ba1-9311-73bffa98cc31" />

# Base 4 — GeoSampa

Shape: 96 linhas e 43 colunas.

Tipos de Dados: nm_distrit (texto); as outras 42 colunas são do tipo inteiro (contemplando a soma de equipamentos como bibliotecas, hospitais, escolas, praças, etc).

Amostra das 5 primeiras linhas (principais colunas):

<img width="566" height="123" alt="image" src="https://github.com/user-attachments/assets/f4f73b98-9034-48f1-bca5-c3b965b9e58e" />

Ranqueamos os 10 distritos paulistanos com a maior infraestrutura de educação pública. Grajaú e Jardim Ângela lideram o ranking de volume de escolas.

<img width="1600" height="800" alt="image" src="https://github.com/user-attachments/assets/d23847f9-2358-444b-9323-4bc32de0bae4" />

# Base 5 — IBGE

Shape: 10.698 linhas e 28 colunas.

Tipos de Dados: CD_DIST, CD_REGIAO, CD_UF, CD_MUN, CD_RGINT e CD_RGI (inteiro); AREA_KM2, v0001 até v0009 e nomenclaturas de regiões/municípios (texto).

Amostra das 5 primeiras linhas (principais colunas):

<img width="577" height="130" alt="image" src="https://github.com/user-attachments/assets/2cf6199c-aff6-431a-869d-23e2fa9e1dd4" />

O dataset do IBGE abrange o Brasil inteiro. Porem como estamos focando na cidade de São Paulo O gráfico horizontal ilustra os 10 municipios com a maior quantidade de distritos mapeados. São Paulo e Mogi das Cruzes lideram o volume de zonas distritais.

<img width="1024" height="572" alt="image" src="https://github.com/user-attachments/assets/5a3c58e7-fb13-4def-b32b-a8d04fe17c35" />








