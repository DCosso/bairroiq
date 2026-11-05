# BairroIQ | Star Schema Delta v1 — contrato de materialização interna

**Estado deste pacote:** código para CI + *dry-run*, com aplicação somente mediante confirmação humana posterior. Nenhuma PR deste pacote cria tabelas por si só. Fonte existente `workspace.gold.distritos_wide` permanece intacta.

## Objetivo

Materializar internamente as sete estruturas validadas do preview v1, como **tabelas Delta gerenciadas no Unity Catalog**, sem liberar o catálogo v3 como produto. O foco é preservar auditoria, grão, chaves e fotografia reprodutível, não criar uma dimensão temporal fictícia nem oferecer uma API pronta.

## Identificação e destino

Snapshot fixado: `v3.0.0-candidato|726091fefefa868fd5d0d2c6929b1d68c4849941f4c7510b4fee0d93a075d38b`.

Nomes físicos propostos no schema `workspace.gold`, todos com prefixo `bairroiq_`:

| Entidade | Tabela física | Grão por snapshot | Registros iniciais |
|---|---|---|---:|
| dim_snapshot | `workspace.gold.bairroiq_dim_snapshot` | 1 por `snapshot_id` | 1 |
| dim_distrito | `workspace.gold.bairroiq_dim_distrito` | (`snapshot_id`, `CD_DIST`) | 96 |
| dim_perfil | `workspace.gold.bairroiq_dim_perfil` | `perfil_sk` | 9 |
| dim_indicador | `workspace.gold.bairroiq_dim_indicador` | `indicador_sk` | 11 |
| fato_distrito_indicador | `workspace.gold.bairroiq_fato_distrito_indicador` | (`snapshot_id`, `CD_DIST`, `indicador_sk`) | 1056 |
| fato_distrito_perfil | `workspace.gold.bairroiq_fato_distrito_perfil` | (`snapshot_id`, `CD_DIST`) | 96 |
| fato_prioridade_ocorrencias | `workspace.gold.bairroiq_fato_prioridade_ocorrencias` | (`snapshot_id`, `CD_DIST`) | 96 |

**Diferença intencional ante o preview pandas:** `dim_distrito` adiciona `snapshot_id` físico. Isso evita que uma alteração de nome ou centroide no futuro reescreva o histórico de outro modelo. Suas chaves não devem ser consultadas ignorando o snapshot.

As outras seis estruturas mantêm as colunas do preview. O campo `ano_snapshot_fonte` da dimensão snapshot **continua NULL**, com tipo Spark explícito `LONG`; isso é deliberado: a Gold wide não possui data de observação universal.

## Política de atualização e imutabilidade

- Um `snapshot_id` sempre é derivado de **versão do catálogo e hash da fonte**, nunca de `current_date` ou data de execução.
- Um snapshot é **append-only e imutável**. Não há `overwrite`, `update`, `merge` ou `delete` de dados existentes.
- Reexecução de um snapshot já materializado verifica conteúdo idêntico; se bater, é operação idempotente sem escrita.
- Em tentativa de recuperação de escrita parcial, uma relação já preenchida só é reaproveitada se todos os seus registros e valores forem idênticos aos esperados; caso contrário, falha sem novas escritas.
- Mudança da Gold fonte, hash, composição, rótulos ou versão exige **nova PR**. O runner congelado não aprova mudança de hash automaticamente.
- Nenhum agendamento, trigger, Job adicional ou aplicação no CI/CD. O CD pode apenas distribuir o script.
- Não criar partições Delta por `snapshot_id` neste volume muito pequeno. O particionamento pode ser reavaliado quando houver massa e frequência que justifiquem.

## Gate de disponibilidade e limitações transacionais

As escritas das sete tabelas **não são uma única transação multi-tabela**. O runner cria/atualiza as seis relações de dados e **registra `dim_snapshot` por último**, exclusivamente após verificar conteúdo, schema e cardinalidade. Na leitura futura, um snapshot só é elegível se aparecer em `bairroiq_dim_snapshot` e todas as relações estiverem conciliadas. Um erro entre tabelas pode deixar registros físicos parciais sem o marcador; não são dados aprovados para consumo.

Não se presume suporte a transações multi-tabela do Unity Catalog na edição/compute do projeto. Para esse recurso, a Databricks exige condições adicionais (por exemplo, catalog commits habilitado).

O `status` do snapshot continua `PREVIA_DIMENSIONAL_NAO_PUBLICAVEL`, `disponivel_publicamente = false` e `periodo_validado_na_gold = false`. Não se deve criar views públicas nem conceder novos `GRANT` por esta PR.

## Temporalidade e agregações

- Empregos formais: indicador documentado como **2021** (dados de vínculos localizados por distrito). Atualização requer revalidação.
- SSP: taxas registradas em janela de 12 meses cujo mês final não está catalogado nesta Gold. **Não inventar data de término**.
- Infraestrutura GeoSampa e densidade: sem referência temporal confiável nessa fotografia wide. Não preencher data de execução.
- Taxas por 100 mil, equipamentos por 10 mil e densidade não devem ser somadas como contagens.
- A preferência de roubos e furtos continua um ranking **relativo aos 96 distritos**, independente dos nove perfis, sem representar nota de segurança individual.

## Operação e segurança

`check(spark)` executa todas as verificações usando a Gold e lê os alvos quando existirem; **nenhuma escrita**.

`apply_snapshot(spark, confirmation=..., expected_hash=...)` é a única operação de escrita e só deve ser invocada em notebook manual após aprovação dos checks de PR e do *dry-run*. Requer permissões de `CREATE TABLE`/`MODIFY` adequadas, e um único escritor simultâneo. Não há opção de publicação pública.

A política de acesso à API, comentários do Unity Catalog, histórico analítico por período, SCD2, lineage de fontes e arquitetura Lambda ficam para PRs posteriores. Este é um primeiro snapshot auditável, não a entrega completa de governança produtiva.
