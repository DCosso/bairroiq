# BairroIQ — Registro de auditorias v3 e gates para homologação

**Data de análise:** 2026-11-05  
**Escopo:** São Paulo, 96 distritos oficiais, ML K-Means K=9, Gold `workspace.gold.distritos_wide`.  
**Snapshot congelado:** `726091fefefa868fd5d0d2c6929b1d68c4849941f4c7510b4fee0d93a075d38b`.  
**Status:** `AUDITORIAS_TECNICAS_CONCLUIDAS_PUBLICACAO_PENDENTE`.

## 1. Evidências do catálogo v3 reproduzido no Databricks

- Nove perfis; 96 distritos únicos; nenhum grupo unitário ou com até dois distritos.
- Silhouette `0.194467`, Davies-Bouldin `1.334164`, Calinski-Harabasz `27.193823`.
- Distribuição dos grupos (ordenada): `6, 6, 7, 7, 8, 9, 12, 19, 22`.
- Três distritos de fronteira com Silhouette individual negativa: **Mooca, Socorro, Lajeado**.
- `publicacao_gold_autorizada=False`, `alteracoes_gold=NENHUMA`.
- Limitação: ARI de estabilidade mediana `0.470918`, ou seja, não atribuir estabilidade forte.

## 2. Evidências da prioridade por roubos e furtos

Auditoria em 96 taxas distritais de crimes patrimoniais registradas, ambas **por 100 mil habitantes**, com comparação por medianas de distritos (não taxa municipal agregada):

| Medida | Mediana dos 96 | Mediana P04 |
|---|---:|---:|
| Roubos | 455.921567 | 301.062930 |
| Furtos | 1212.697723 | 650.382101 |

- P04: 22 distritos.
- Em 19/22 (86,36%), **ambas** as taxas estão abaixo das respectivas medianas dos 96 distritos.
- Condição editorial para o título candidato **“Menos Roubos e Furtos”**: `True`.
- Nome homologado para divulgação pública: `False`.
- **Exceções:** Jardim Ângela, Artur Alvim e Guaianases não têm a taxa de roubos abaixo da mediana na mesma verificação.
- A prioridade por ocorrências continua separada dos clusters, com 50% percentil de roubos e 50% percentil de furtos; não representa probabilidade de vitimização ou nota geral de segurança.
- Janela final exata dos 12 meses deve ser recuperada dos metadados da fonte antes da divulgação pública.

## 3. Indicador de empregos formais e P07

- `workspace.silver.observasampa_indicadores_distrito` e Gold conciliadas em **96/96 distritos**, zero divergências.
- Granularidade observada na Silver: registros identificados por distrito. O processo de ingestão filtra explicitamente regiões nomeadas com `(Distrito)`.
- Indicador: `Empregos formais no município - Total`, com **ano 2021** em todos os 96 distritos.
- 96 valores distintos; mediana entre distritos de **30.815** e máximo **464.251** (Saúde).
- Os 96 totais correspondem à soma dos cinco setores (Agropecuária, Comércio, Construção, Indústria, Serviços), com zero divergências numéricas e soma de **4.751.860** vínculos.
- O caso Saúde soma **446.367 em Serviços**, 10.465 em Comércio, 5.728 em Construção, 1.686 em Indústria e 5 em Agropecuária = 464.251.
- Nome candidato mantido: **“Empregos em Destaque”**.
- Interpretação responsável: concentração de vínculos formais no snapshot de 2021. Não deduzir facilidade de encontrar emprego, salário, deslocamento ou oferta atual de vagas.
- A documentação metodológica oficial de localização dos vínculos deve permanecer referenciada no catálogo antes da divulgação. A atualização para anos mais recentes exige refazer e versionar o modelo, nunca trocar os valores silenciosamente.

## 4. Governança: o que foi e o que NÃO foi aprovado

**Aprovado tecnicamente:** reprodução v3, consistência Silver/Gold para o indicador empregado, soma setorial de 2021, condição editorial do nome P04, critério independente de ordenação por ocorrências.

**Não homologado automaticamente:** uso público dos nove cartões de perfil; interpretação de segurança individual; dados atuais de emprego; calendário de referência de todas as fontes; modelos de recomendação residencial; fatos físicos de consumo. As saídas v3 originais seguem marcadas `CANDIDATO_REVISAO_SEMANTICA` / `EXPLORATORIO_NAO_HOMOLOGADO`.

## 5. Gates antes de criar Delta de consumo

1. Executar o preview dimensional v1 na Gold real e conferir chaves/contagens.
2. Validar `periodo_referencia` de cada fonte na Silver, especialmente os 12 meses da SSP e os equipamentos GeoSampa. **Não** usar data de execução nem hash como data da observação.
3. Revisar microcopy e ressalvas dos nove cartões com o responsável pelo front-end.
4. Definir explicitamente a política de atualização, retenção de snapshots e evolução v3 → v4.
5. Criar PR separado para DDL físico/particionamento e controle de publicação. Nenhuma promoção automática nesta entrega.

## 6. Fontes de evidência internas

- `docs/ml/execucao_databricks_catalogo_v3.md`
- `docs/ml/execucao_prioridade_ocorrencias_v1.md`
- `docs/ml/metodologia_catalogo_perfis_v3.md`
- `docs/dicionario_gold_distritos_wide.json`
- Outputs CSV das execuções manuais do Databricks em 2026-11-05, revisados nesta etapa. Esses arquivos não são reproduzidos no repositório nem constituem fixtures para os testes automatizados.
