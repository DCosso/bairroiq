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

# Shape: 10,698 linhas x 28 colunas

<img width="228" height="581" alt="image" src="https://github.com/user-attachments/assets/230af33d-8e15-4fa9-83c6-81cba81aca81" />

# Valores ausentes:

<img width="227" height="321" alt="image" src="https://github.com/user-attachments/assets/97ead1d0-198e-4a44-90ee-c3266187fe32" />

# Cobertura geográfica:

<img width="414" height="81" alt="image" src="https://github.com/user-attachments/assets/26bf712a-edff-4969-a872-4e5658fb0187" />

# Amostra (primeiras 5 linhas, colunas selecionadas):

<img width="790" height="121" alt="image" src="https://github.com/user-attachments/assets/74cc2e26-97f1-4f1f-bab8-a40065704472" />

# Base 3 — ObservaSampa (Dados Demograficos)

A análise da base, permitiu observar a evolução da população de São Paulo ao longo do período disponivel analisado. Essa visualização contribui para compreender as mudanças no perfil demográfico da cidade e contextualizar os demais indicadores utilizados no BairroIQ.

# Shape: 1,434 linhas x 4 colunas

Colunas: ['Nome', 'Região', 'Período', 'Resultado']

<img width="134" height="101" alt="image" src="https://github.com/user-attachments/assets/f25c6741-7f02-486b-9855-b9ab2b558e7a" />

# Valores ausentes:

Nenhum valor ausente

<img width="207" height="101" alt="image" src="https://github.com/user-attachments/assets/51567cda-8d94-4736-ab33-037c6517757a" />

Top 10 indicadores por frequência:
Nome
01.01.01 Quantidade de famílias em situação de extrema pobreza (até 1/4 salário mínimo)                                     129
11.01.03 Número de Unidades Habitacionais entregues (por meio de programas habitacionais e parcerias firmadas)              129
11.01.08 Total de famílias beneficiárias de Auxílio Aluguel por ano                                                         129
11.01.07 Número estimado de domicílios em favelas                                                                           129
01.02.01 Quantidade de famílias em situação de pobreza (renda por pessoa de ⅛ até ¼ de salário-mínimo)                      129
01.05.02 Número de famílias em atendimento habitacional provisório (Auxílio Aluguel) por situação de risco e emergência     129
01.02.02 Quantidade de famílias em situação de baixa renda (renda por pessoa de ¼ até ½ salário mínimo)                     129
01.05.03 Famílias em atendimento habitacional provisório por situação de risco e emergência (%)                             100
16.0a.01 Número de câmeras inseridas no Projeto City Câmeras                                                                 33
16.04.01 Número de armas recolhidas pela Campanha do Desarmamento pela Guarda Civil Metropolitana - GCM                      33

# Amostra (primeiras 5 linhas):
                                                                                      
<img width="930" height="121" alt="image" src="https://github.com/user-attachments/assets/15bda79a-4b4a-481d-90bc-a16c70518082" />



