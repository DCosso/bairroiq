# BairroIQ | Star Schema Delta v1 — validação de instalação e dry-run

**Executar somente após merge e CD desta PR.** Primeira execução em notebook Python Databricks; usa a Gold real sem gravá-la.

```python
from pathlib import Path
import importlib.util
import json

BUNDLE = Path(
    '/Workspace/Users/42be9e1b-1ab5-4a46-96a7-0a4691c31b5d/'
    '.bundle/barrioiq_pipeline/dev/files'
)
REQUIRED = [
    'star_schema_v1_delta_runner.py',
    'star_schema_v1_preview.py',
    'prioridade_roubos_furtos_v1.py',
    'ml_catalogo_perfis_v3.py',
    'ml_perfis_territoriais_v2.py',
    'catalogo_perfis_v3_config.json',
    'distritos_centroides_ibge_2022.json',
]
for filename in REQUIRED:
    path = BUNDLE / filename
    if not path.is_file():
        raise FileNotFoundError(f'Ausente no Bundle: {path}')

path = BUNDLE / 'star_schema_v1_delta_runner.py'
spec = importlib.util.spec_from_file_location('bairroiq_delta_v1', str(path))
delta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delta)

print('BAIRROIQ | DELTA V1 | DRY RUN, SEM ESCRITAS')
plano = delta.check(spark)
print(json.dumps(plano, ensure_ascii=False, indent=2))
assert plano['will_write_on_check'] is False
assert plano['publicacao_gold_autorizada'] is False
assert len(plano['tables']) == 7
print('BAIRROIQ_DELTA_V1_DRY_RUN_VALIDATED')
```

O plano retorna para cada uma das sete tabelas: se existe, quantas linhas daquele snapshot já possui e o que **aconteceria** numa aplicação manual. No primeiro uso, é esperado `table_exists=false` e `action_if_applied=APPEND_SNAPSHOT` para todas.

**Não executar a aplicação na mesma etapa.** Encaminhar o output completo para revisão de colisão de nomes, permissões e estado dos destinos antes da primeira escrita. O `check` não executa comandos DDL ou DML; no entanto, precisa de acesso de leitura às tabelas de destino que já existirem.

## Aplicação posterior (somente após confirmação explícita)

A chamada manual autorizada estará disponível no módulo:

```python
# NAO EXECUTAR ATE A APROVACAO DO PLANO E DOS DESTINOS.
# resultado = delta.apply_snapshot(
#     spark,
#     confirmation='MATERIALIZAR_SNAPSHOT_INTERNO_SEM_PUBLICACAO',
#     expected_hash='726091fefefa868fd5d0d2c6929b1d68c4849941f4c7510b4fee0d93a075d38b',
# )
# print(json.dumps(resultado, ensure_ascii=False, indent=2))
```

Se autorizado depois: (1) calcula a prévia e hash real; (2) verifica os sete alvos; (3) escreve apenas ausentes, sem sobrescrever; (4) compara conteúdo escrito; (5) grava `dim_snapshot` por último; (6) reaudita o estado. Essa sequência **não garante atomicidade multi-tabela**. Um erro interrompe o processo e requer investigação antes de uma nova tentativa.

## Problemas esperados

- `BAIRROIQ_DELTA_V1_BLOCKED`: hash, versão, estado, tipos, FKs, schema ou conteúdo divergente.
- Falta de permissão ao catalog/schema: registrar a exceção e verificar autorização no Unity Catalog; **não** trocar arbitrariamente para outro catálogo.
- Nova versão dos dados fonte: criar nova proposta de snapshot/versionamento, não ignorar o hash.
- Nenhuma tabela deve ser criada automaticamente apenas por integrar a PR; o CD existente preserva os sete jobs.

## Compatibilidade de escrita Serverless

O escritor utiliza somente `DataFrameWriter.mode("append").saveAsTable(...)`,
com validação do estado do destino imediatamente antes de cada operação.
No caso de tabela ainda ausente, `append` pode criá-la; no caso de tabela
preexistente, acrescenta somente o snapshot previamente auditado.
O uso de `errorifexists` foi removido devido a uma falha já observada no
workspace Serverless. Isto não implica suporte a escritores concorrentes.
O primeiro uso real de `apply_snapshot` requer aprovação explícita e deve
continuar separado do dry-run.
