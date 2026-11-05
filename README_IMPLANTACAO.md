# BairroIQ | Próxima PR — Star Schema Delta v1, preparado para materialização interna

## Resultado já validado

O preview dimensional com Gold real completou: dim_snapshot 1, dim_distrito 96, dim_perfil 9, dim_indicador 11, fato_distrito_indicador 1056, fato_distrito_perfil 96, fato_prioridade_ocorrencias 96. Hash da Gold `726091fefefa868fd5d0d2c6929b1d68c4849941f4c7510b4fee0d93a075d38b`. Sem alterações da Gold. A execução está registrada na conversa; os sete CSVs compartilhados eram apenas a amostra de dez linhas exibida pelo notebook, **não dumps completos**.

## Arquivos para colocar no repo (preservar caminhos)

- `barrioiq_pipeline/star_schema_v1_delta_runner.py`
- `tests/test_star_schema_v1_delta_runner.py`
- `.github/workflows/star-schema-delta-v1-ci.yml`
- `docs/modelagem/star_schema_v1_delta_contrato.md`
- `docs/modelagem/star_schema_v1_delta_execucao_databricks.md`

**Não colocar o README_IMPLANTACAO.md no repo.** Ele é apenas a instrução do pacote.

## Git

Criar branch **a partir da main atual**: `feature/star-schema-delta-v1`.

Commit:

`feat(gold): prepare guarded Delta snapshots for star schema v1`

Título da PR:

`feat(gold): prepare guarded Delta snapshots for star schema v1`

### Descrição pronta para PR

```markdown
## Motivação
O Star Schema v1 passou na validação de dados reais, incluindo 7 estruturas, 96 distritos, 9 perfis, 11 indicadores e 1.056 fatos de indicadores. A etapa atual prepara a materialização física segura em tabelas Delta gerenciadas, com preservação do snapshot v3 auditado.

## Escopo
- Runner Delta interno com dry-run read-only e aplicação manual bloqueada por frase de confirmação e hash fixado.
- 7 destinos físicos versionados por snapshot_id em workspace.gold, prefixo barrioiq_.
- Dimensão de distrito versionada fisicamente, evitando sobrescrita de nomes/centroides históricos.
- Integridade de chaves, FK, cardinalidade, tipo, conteúdo e formato Delta.
- Snapshots imutáveis, reexecução idempotente e detecção de inconsistência em cargas parciais.
- Registro de dim_snapshot por último como marcador de completude, sem presumir transação multi-tabela.
- CI e documentação de operação e ressalvas temporais.

## Segurança
- Nenhuma escrita ocorre no CI/CD ou no merge da PR.
- Nenhum job é criado/modificado; os 7 jobs protegidos continuam iguais.
- Nenhum GRANT, API, view pública ou perfil homologado.
- Fonte workspace.gold.distritos_wide intacta; sem atualizar o hash ou modelo v3.
- Periodicidade dos indicadores preservada como documentada; sem inventar anos.

## Aceite
- [ ] CI Delta v1 aprovado com dados sintéticos.
- [ ] CI Bundle e validações gerais aprovados.
- [ ] Deploy da main confirmado com 7 jobs preservados.
- [ ] Notebook `delta.check(spark)` executado com dados reais, sem escritas.
- [ ] Destinos e permissões revisados antes de autorização para `apply_snapshot`.

## Fora do escopo
Escrita Delta imediata, publicação pública, SCD2, atualizações automáticas, Lambda/streaming, dim_tempo analítica e API do front-end.
```

## Testes locais executados

No pacote foram validados os contratos com testes sintéticos Python. O módulo ainda **não** foi testado com escrita Delta real. Após merge, executar primeiro apenas a célula de dry-run descrita em `docs/modelagem/star_schema_v1_delta_execucao_databricks.md`.


## Revisão de compatibilidade Serverless (pre-merge)

Este pacote substitui a versão anterior devido ao `errorifexists` usado
na função `_write_one`. Use os arquivos **inteiros** desta versão.

A branch já foi criada e recebeu push. Substitua apenas os arquivos alterados:

- `barrioiq_pipeline/star_schema_v1_delta_runner.py`
- `tests/test_star_schema_v1_delta_runner.py`
- `.github/workflows/star-schema-delta-v1-ci.yml`
- `docs/modelagem/star_schema_v1_delta_execucao_databricks.md`

Depois faça commit e push com a mensagem:
`fix(gold): use serverless-compatible append writer for Delta snapshots`

Não execute `apply_snapshot` nem crie a PR antes de validar os novos checks.
