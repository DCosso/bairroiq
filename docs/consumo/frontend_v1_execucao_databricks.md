# BairroIQ — Executar frontend v1 do Bundle (read-only)

Após merge na `main` e deploy do Bundle com os sete jobs preservados, executar **uma célula Python** em notebook Databricks:

```python
from pathlib import Path
import importlib.util
import json

BUNDLE = Path(
    '/Workspace/Users/42be9e1b-1ab5-4a46-96a7-0a4691c31b5d/'
    '.bundle/barrioiq_pipeline/dev/files'
)
REQUIRED = (
    'frontend_v1_runner.py', 'star_schema_v1_delta_runner.py',
    'star_schema_v1_preview.py', 'prioridade_roubos_furtos_v1.py',
    'ml_catalogo_perfis_v3.py', 'ml_perfis_territoriais_v2.py',
    'catalogo_perfis_v3_config.json',
    'distritos_centroides_ibge_2022.json',
)
for name in REQUIRED:
    assert (BUNDLE / name).is_file(), f'Ausente no Bundle: {name}'

spec = importlib.util.spec_from_file_location(
    'bairroiq_frontend_v1_readonly', str(BUNDLE / 'frontend_v1_runner.py')
)
frontend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frontend)
result = frontend.run_from_spark(spark)
print('BAIRROIQ | FRONTEND V1 | SOMENTE LEITURA')
print(json.dumps(result['resumo'], indent=2, ensure_ascii=False))
assert result['resumo']['distritos'] == 96
assert result['resumo']['clusters'] == 9
assert result['resumo']['escrita_executada'] is False
assert result['resumo']['publicacao_autorizada'] is False
assert result['resumo']['indicadores_led_preenchidos'] == 96
assert result['resumo']['arborizacao_valores_preenchidos'] == 0
assert list(result['visual'].columns) == list(frontend.VISUAL_COLUMNS)
print('\nFORMATO VISUAL - 96 DISTRITOS')
display(result['visual'])
print('\nCONTRATO TECNICO - 12 LINHAS')
display(result['tecnico'].head(12))
print('BAIRROIQ_FRONTEND_V1_VERSIONED_READ_ONLY_VALIDATED')
```

Este módulo carrega as sete estruturas de snapshot e os campos de LED da Gold, executa o preflight Delta (somente leitura) e calcula os percentis locais entre exatamente 96 distritos. Não materializa a tabela física, nem publica API ou altera privilégios. **Não chamar `apply_snapshot`** nesta etapa.

Se a validação retornar `BAIRROIQ_FRONTEND_V1_BLOCKED`, não relaxar os guardrails: diagnosticar a fonte e o contrato.
