# BairroIQ — Star Schema e arquitetura Lambda (escopo acadêmico)

**Fonte do requisito:** briefing *Hands-On Engenharia de Dados em Big Data e Analytics*, p. 19 (entregáveis: "Arquitetura Lambda em Nuvem"; "Modelagem de Dados: Star Schema ... Wide Table ..."). Na p. 17, também é solicitado um pequeno Data Lake/Lakehouse com camadas Bronze/Silver/Gold. **O Lakehouse e a Wide Table já existem; Star Schema e Lambda ainda não estão implementados e não devem ser anunciados como prontos.**

## 1. Objetivo e princípio

Não reconstruir a Gold física `workspace.gold.distritos_wide`: ela foi validada com 96 linhas e 254 colunas. Entregar uma modelagem dimensional **separada para OLAP** e um **piloto demonstrável** de dois caminhos de processamento, sob a mesma governança e sem serviço cloud pago adicional obrigatório.

## 2. Star Schema mínimo proposto

```text
             dim_distrito (CD_DIST; 96 distritos)
                         |
                         v
                 fato_indicador_distrito
                         ^
                         |
                 dim_indicador (id_indicador)
```

- **`workspace.gold.dim_distrito`:** um registro por distrito oficial (`CD_DIST`, `NM_DIST` oficial, latitude, longitude). Chave `CD_DIST` única.
- **`workspace.gold.dim_indicador`:** uma linha por indicador selecionado, com ID estável, nome de exibição, fonte, unidade, classificação e observação metodológica (descrições ancoradas no dicionário JSON já versionado, não adivinhadas).
- **`workspace.gold.fato_indicador_distrito`:** **grão distrito × indicador × snapshot explicitamente identificado**, com `CD_DIST`, `id_indicador`, `valor_numerico` (nulos preservados no contrato adequado) e hash/versão de fonte. Nunca somar taxas ou percentuais automaticamente.

O snapshot Gold integra referências temporais diferentes: **não fabricar uma `dim_data` única a partir de `CURRENT_DATE()`**, nem alegar série temporal na Wide Table. Caso seja necessário OLAP temporal, usar dados Silver com período verificável, como `workspace.silver.imoveis_bairro_mensal` (`mes`, `bairro_normalizado`, `transacao`, `mediana_m2`, `novos_anuncios`, `anuncios_ativos_media_dia`). Para o mercado imobiliário, a correspondência bairro→distrito só é válida onde houver aprovação no de/para. **Não calcular preço distrital como média simples de medianas de bairros.**

**Validação esperada:** unicidade das dimensões, integridade referencial e ausência de duplicação ao agregar. Publicação controlada em tabelas distintas, sem modificar a Gold consolidada. Documentar diagramas físico/lógico, SQL/runner, testes, evidência de execução e exemplo de consulta OLAP. **Status: PENDENTE**.

## 3. Arquitetura Lambda — o que é e como demonstrar

A arquitetura Lambda clássica tem pelo menos **três funções lógicas**: caminho batch para recomputação histórica, caminho speed para novos eventos com menor latência, e serving view que combina os resultados de forma consistente. **Não é a mesma coisa que usar AWS Lambda como função serverless**, nem é equivalente a Bronze/Silver/Gold. O briefing pede "Arquitetura Lambda em Nuvem", portanto a entrega acadêmica exige demonstração concreta; somente desenhar o diagrama não basta para alegar implementação.

```text
          Dataset / evento de entrada versionado
                       |
                 +-----+-----+
                 |           |
                 v           v
           CAMINHO BATCH   CAMINHO SPEED
         Reprocessa lote   Consome pequenos lotes
         e/ou histórico    (microbatch ou trigger)
                 |           |
                 v           v
           batch_result    speed_result
                 +-----+-----+
                       |
                       v
                 SERVING VIEW
           Mesma chave e regra;
        compõe sem contar registros 2x
```

### MVP de custo controlado

1. Definir **um único indicador demonstrável**, por exemplo contagem incremental de novos anúncios (`novos_anuncios`) em uma amostra versionada; manter `mes`, `bairro_normalizado` e `transacao` como chaves existentes.
2. Caminho batch: reprocessar a amostra histórica na camada de leitura.
3. Caminho speed: processar pequenas entradas novas por microbatch/execução pontual. Validar antes as capacidades reais do plano Databricks Free; **não prometer streaming contínuo ou jobs agendados se o ambiente não permitir**.
4. Serving: reconciliar o mesmo indicador por chave, evitando duplicidade; comparar com recomputação de controle e guardar logs da execução.
5. Demonstrar no notebook a chegada de novo lote, o cálculo speed, a recomputação batch e a igualdade da serving view final.

Caso o plano gratuito não permita um `Structured Streaming` completo, documentar a restrição e implementar protótipo com microbatches disparados manualmente para demonstrar a lógica das camadas. **Isso será uma simulação do caminho speed, não um serviço de streaming contínuo implantado.** A apresentação deve distingui-los.

## 4. Critérios de aceite

| Entrega | Aceite | Estado |
|---|---|---|
| Gold Wide | 96 distritos, 254 atributos, contrato e validações | Concluída |
| ML comparativo | 2 algoritmos, K=2..12 e K=10, métricas, estabilidade, análises de sensibilidade | Experimento em desenvolvimento |
| Star Schema | 2 dimensões + 1 fato, dados reais, consultas OLAP e qualidade | **Pendente** |
| Lambda | Lote + caminho speed + serving + demonstração de consistência | **Pendente** |
| Front-end | Uso dos dados reais, diferenças claras entre indicadores e scores, perfil de distrito | Equipe de interface |
| Documentação final | README, metodologia, SQL/notebooks, diagrama, apresentação e evidências | **Pendente** |

**Ordem recomendada:** consolidar a comparação de ML e seus artefatos → Star Schema mínimo com dados reais → Lambda piloto sem custo obrigatório → contrato de consumo, integração e apresentação. Isso satisfaz melhor a rubrica do trabalho sem expandir indefinidamente a engenharia.
