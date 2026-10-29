# Disciplina: Hands-On Fundamentos de Dados e Analytics

Módulo 1 – MBA em Engenharia de Dados – Universidade Presbiteriana Mackenzie

Mentoria: Prof. Gustavo Ferreira
   
Nome do Projeto: BairroIQ — Inteligência Geográfica para Moradia e Negócios.

# Setor de Atuação: 

( ) Varejo 

( ) Saúde 

( ) Finanças

( ) Logística 

( ) Setor Público 

(X) Outro: Imobiliário.

# Integrantes:

[Aline Ferreira](https://www.linkedin.com/in/aline-ribeiro-ferreira-55a8a8185/)

[Arthur Girotti](https://www.linkedin.com/in/arthurgirotti/) 

[Douglas Cosso](https://www.linkedin.com/in/douglascosso/)

[Igor Sousa](https://www.linkedin.com/in/igor-oliveira-177690134/) 

[Lais Hatsumi](https://www.linkedin.com/in/laissato/) 	

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

# Base 2 — IBGE (Censo 2022)
Shape: 10,698 linhas x 28 colunas

<img width="228" height="581" alt="image" src="https://github.com/user-attachments/assets/230af33d-8e15-4fa9-83c6-81cba81aca81" />

# Valores ausentes:

<img width="227" height="321" alt="image" src="https://github.com/user-attachments/assets/97ead1d0-198e-4a44-90ee-c3266187fe32" />

# Cobertura geográfica:

<img width="414" height="81" alt="image" src="https://github.com/user-attachments/assets/26bf712a-edff-4969-a872-4e5658fb0187" />

# Amostra (primeiras 5 linhas, colunas selecionadas):

<img width="790" height="121" alt="image" src="https://github.com/user-attachments/assets/74cc2e26-97f1-4f1f-bab8-a40065704472" />

# Base 3 — ObservaSampa (Dados Demograficos)
Shape: 1,434 linhas x 4 colunas

A análise da base, permitiu observar a evolução da população de São Paulo ao longo do período disponivel analisado. Essa visualização contribui para compreender as mudanças no perfil demográfico da cidade e contextualizar os demais indicadores utilizados no BairroIQ.

<img width="134" height="101" alt="image" src="https://github.com/user-attachments/assets/f25c6741-7f02-486b-9855-b9ab2b558e7a" />

# Valores ausentes:

Nenhum valor ausente

<img width="207" height="101" alt="image" src="https://github.com/user-attachments/assets/51567cda-8d94-4736-ab33-037c6517757a" />

# Top 15 Distritos com Familias em Extrema Pobreza (2025)

Com essa exploração e possivel alinhar Pilares para os critérios de Custo de Vida e Oportunidades. Distritos com alta concentração de extrema pobreza (como Grajaú e Jardim Ângela) tendem a apresentar dinâmicas imobiliárias e de consumo completamente diferentes de distritos que não aparecem neste top 15.

Identificação de Outliers: O Grajaú descola significativamente do resto da lista, ultrapassando as 17.500 famílias. Para um modelo de Machine Learning, este é um dado vital que pode forçar a criação de um cluster isolado ou alterar o centroide de um grupo periférico.

<img width="1000" height="600" alt="image" src="https://github.com/user-attachments/assets/2f80ceb1-9afd-497a-b879-8d3763a9fcd3" />

# Amostra (primeiras 5 linhas):
                                                                                      
<img width="930" height="121" alt="image" src="https://github.com/user-attachments/assets/15bda79a-4b4a-481d-90bc-a16c70518082" />

# Base 4 — Dados de preços de imóveis - (Guru dos Imóveis)

Shape: 29.612 linhas x 9 colunas

Ao analisá-lo essa base, identificamos o histórico de preços do mercado imobiliário em São Paulo. Isto contribui para o pilar de Custo de Vida (referências de preços de moradia).

Como a base tem os valores separados por linhas (aluguer numa linha, venda noutra) e tem o histórico de vários meses, o papel da Engenharia de Dados aqui é filtrar o mês mais recente, separar o que é aluguer do que é venda, e calcular a média (ou agrupar) para cruzar com os Distritos.

<img width="1600" height="960" alt="image" src="https://github.com/user-attachments/assets/26aa9fd4-5f34-4413-a1fb-62ba2c5d77d2" />

# Base 5 - Dados de infraestrutura urbana - GeoSampa
Shape: 100 linhas x 43 colunas

# Amostra (primeiras 5 linhas):

<img width="1047" height="121" alt="image" src="https://github.com/user-attachments/assets/c573773b-8a5b-48d8-873f-131b46d708dc" />

A análise dos distritos com maior volume de infraestrutura permitiu identificar as regiões que concentram a maior quantidade de equipamentos e serviços registrados na base de dados. Essa visualização contribui para compreender como a infraestrutura está distribuída pelo município de São Paulo e comparar os distritos quanto à disponibilidade dos recursos considerados na análise. 

Com essa analise foi possivel observar a Extrema Desigualdade (Outliers no Topo): O distrito do Grajaú é um outlier massivo em volume absoluto de serviços, superando os 950 equipamentos mapeados, seguido por Itaquera e Jardim São Luís. É importante notar, no entanto, que muitos destes distritos no topo são geograficamente gigantescos e muito populosos, o que explica a alta concentração absoluta de equipamentos (como escolas públicas e pontos de autocarro).

Desertos de Infraestrutura (Bottom 10): No extremo oposto, distritos como Marsilac e Pari possuem menos de 150 equipamentos públicos/serviços registados na soma de todos os pilares.

Padrões para Clusterização: Este gráfico prova que a base de dados que construiu conseguiu captar a variância urbana. Os algoritmos de Machine Learning vão conseguir segmentar a cidade perfeitamente, cruzando este "volume de infraestrutura" com as métricas de Custo de Vida (Guru dos Imóveis) e Renda (ObservaSampa) mapeáados anteriormente.

<img width="1600" height="1067" alt="image" src="https://github.com/user-attachments/assets/0634b946-9352-4c19-8c89-16593c6f589a" />


