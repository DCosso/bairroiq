# BairroIQ — Inteligência Geográfica para Moradia e Negócios

## Sobre o projeto

O BairroIQ é um projeto de Engenharia de Dados que busca integrar indicadores públicos para apoiar decisões sobre onde morar ou trabalhar na cidade de São Paulo.

A solução pretende transformar dados dispersos em informações comparáveis por meio de um ranking explicável e de técnicas de clusterização, permitindo identificar regiões com características urbanas semelhantes.

## Problema de negócio

A escolha de uma região para morar ou trabalhar envolve fatores como custo de vida, segurança, mobilidade, infraestrutura, oportunidades de emprego e serviços.

Entretanto, essas informações estão distribuídas em diferentes fontes, com variações de metodologia, atualização e granularidade geográfica, dificultando uma análise integrada.

O BairroIQ busca responder à seguinte pergunta:

**Qual é a melhor região de São Paulo para morar ou trabalhar, considerando orçamento, segurança, mobilidade, infraestrutura, oportunidades e estilo de vida?**

## Objetivo

Desenvolver um MVP que demonstre a integração de dados públicos, o cálculo reproduzível de um ranking, a explicação dos resultados e a identificação de perfis urbanos por clusterização.

## Pilares de análise

| Pilar | Objetivo |
|---|---|
| Custo de vida | Analisar referências de preços de moradia e outros custos disponíveis. |
| Segurança | Avaliar indicadores públicos relacionados à criminalidade. |
| Mobilidade | Investigar transporte público e conectividade urbana. |
| Infraestrutura | Considerar parques, equipamentos urbanos e serviços públicos. |
| Empregos e serviços | Analisar atividades econômicas, estabelecimentos e oportunidades. |

## Escopo geográfico

O escopo inicial será a cidade de São Paulo. A análise priorizará os distritos oficiais quando esse for o nível territorial compatível entre as fontes, com possibilidade de expansão para bairros conforme a disponibilidade de dados.

## Entrega final

O produto será uma aplicação web interativa para:

- Consultar e explorar o ranking das regiões.
- Comparar áreas por dimensão.
- Visualizar indicadores e mapas.
- Identificar perfis urbanos por clusterização.
- Consultar fontes, metodologia e limitações dos resultados.

## Arquitetura e tecnologias previstas

O projeto contemplará uma arquitetura Lambda em nuvem, com caminhos de processamento batch e incremental, camadas Bronze, Silver e Gold, modelagem Star Schema e Wide Table, além de CI/CD e infraestrutura como código.

**Stack proposta:** .

