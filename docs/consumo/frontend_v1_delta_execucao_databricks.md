# BairroIQ | Executar materializador Delta do frontend v1

**Pré-requisitos:** PR integrada à main, GitHub CI e deploy do Bundle aprovados. Não executar escrita a partir de branch não integrada.

## Passo 1 — auditoria somente leitura

```python
from pathlib import Path
import importlib.util
import json

BUNDLE = Path(
    '/Workspace/Users/42be9e1b-1ab5-4a46-96a7-0a4691c31b5d/'
    '.bundle/barrioiq_pipeline/dev/files'
)
SCRIPT = BUNDLE / 'frontend_v1_delta_runner.py'
assert SCRIPT.is_file(), f'Runner não implantado: {SCRIPT}'
assert (BUNDLE / 'frontend_v1_runner.py').is_file()

spec = importlib.util.spec_from_file_location('bairroiq_frontend_delta_v1', str(SCRIPT))
assert spec is not None and spec.loader is not None
consumer_delta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(consumer_delta)

plano = consumer_delta.check(spark)
assert plano['snapshot_id'] == consumer_delta.SNAPSHOT_ID
assert plano['expected_rows'] == 96
assert plano['will_write_on_check'] is False
assert plano['publicacao_autorizada'] is False

print('BAIRROIQ | FRONTEND DELTA V1 | DRY RUN')
print(json.dumps(plano, indent=2, ensure_ascii=False))
print('BAIRROIQ_FRONTEND_DELTA_V1_DRY_RUN_VALIDATED')
```

**PARE após este passo e registre** `payload_sha256`, `action_if_applied` e `rows_in_snapshot`. Nenhuma escrita foi realizada.

## Passo 2 — materialização manual (somente após revisão do dry run)

Execute em notebook separado e **somente após aprovação**. Substitua o valor do SHA pelo retornado pelo passo 1; não invente hash nem execute em paralelo:

```python
# Exemplo de assinatura; NÃO EXECUTAR sem hash concreto validado.
# consumer_delta.apply_snapshot(
#     spark,
#     confirmation='MATERIALIZAR_FRONTEND_V1_INTERNO_SEM_PUBLICACAO',
#     expected_snapshot_id=consumer_delta.SNAPSHOT_ID,
#     expected_payload_sha256='<SHA256_EXATO_DO_CHECK>',
# )
```

## Passo 3 — reconciliação pós-escrita

```python
# Executar somente após a materialização manual autorizada.
# pos = consumer_delta.check(spark)
# assert pos['action_if_applied'] == 'KEEP_VERIFIED'
# assert pos['rows_in_snapshot'] == 96
# print('BAIRROIQ_FRONTEND_DELTA_V1_FULL_SNAPSHOT_VERIFIED')
```

A escrita é idempotente mas **não protege contra dois operadores concorrentes**. Nenhum Job do Bundle deve invocar `apply_snapshot` automaticamente.
