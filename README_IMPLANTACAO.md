# BairroIQ | PR Star Schema v1 — Preview somente leitura

## Onde cada arquivo deve ficar

**ATENÇÃO:** os arquivos dentro deste ZIP já têm os caminhos relativos à **raiz do repositório**. Não coloque todos na raiz, não aninhe a pasta `bairroiq_star_schema_v1_previa` dentro do repo e não substitua a Gold existente.

- `barrioiq_pipeline/star_schema_v1_preview.py`
- `tests/test_star_schema_v1_preview.py`
- `.github/workflows/star-schema-v1-preview-ci.yml`
- `docs/governanca/encerramento_auditoria_semantica_v3.md`
- `docs/modelagem/star_schema_v1_contrato.md`
- `docs/modelagem/star_schema_v1_execucao_databricks.md`

## Commit e PR

Branch sugerida: `feature/star-schema-v1-preview`

Commit:

```text
feat(gold): add read-only star schema preview with audited ML v3 snapshot
```

Título PR:

```text
feat(gold): add read-only star schema preview with audited ML v3 snapshot
```

Descrição sugerida:

```markdown
## Contexto

BairroIQ classifica 96 distritos oficiais de São Paulo em nove perfis ML v3, com uma preferência independente por menores taxas registradas de roubos e furtos. A Gold atual é uma tabela wide com um snapshot sem períodos de origem completos por indicador.

## Objetivo

Criar a primeira constelação dimensional em memória para separar dimensões conformadas, fatos de indicadores, atribuição a perfis e prioridade de ocorrências, preservando a Gold atual.

## Escopo

- Quatro dimensões: snapshot (1), distrito (96), perfil (9), indicador (11).
- Três fatos: distrito-indicador (1056), distrito-perfil (96), prioridade de ocorrências (96).
- Validações de cardinalidade, grão, unicidade, FKs, hash Gold, bloqueio editorial, status e temporalidade.
- Evidências das auditorias de emprego 2021 e P04 registradas na documentação.
- Código de execução somente leitura no Databricks e novo workflow CI.

## Segurança e limitações

- Nenhuma tabela Delta é criada ou atualizada.
- Os resultados NÃO estão homologados publicamente.
- A dimensão snapshot NÃO substitui a data de referência das fontes.
- A publicação física e a historização por período terão PR própria.
- A comparação por ocorrências NÃO é uma nota de segurança.
- A classificação por perfil NÃO é uma recomendação de moradia.

## Testes e critérios de aceite

- [ ] CI Star Schema v1 aprovado com testes artificiais.
- [ ] CI Bundle aprovado.
- [ ] CD na main concluído sem alterar os sete jobs previstos.
- [ ] Preview executado na Gold real e sete contagens conferidas.
- [ ] Nenhuma escrita na Gold.
- [ ] Evidências e pendências da homologação preservadas.

## Fora do escopo

DDL físico, SCD2, fato temporal real, API do front, Lambda/streaming.
```

## Próximo passo depois do merge

Executar a célula de `docs/modelagem/star_schema_v1_execucao_databricks.md` e enviar os outputs. Somente depois iniciar uma PR independente para as tabelas Delta de consumo.
