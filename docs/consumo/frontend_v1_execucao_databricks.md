# BairroIQ — Contrato Frontend v1 de seis colunas — execução no Databricks

Execute **após o merge na main e o deploy do Bundle**. Essa célula não grava dados:

```python
from pathlib import Path
import importlib.util
import json

BUNDLE = Path(
    "/Workspace/Users/42be9e1b-1ab5-4a46-96a7-0a4691c31b5d/"
    ".bundle/barrioiq_pipeline/dev/files"
)
REQUIRED = (
    "frontend_v1_runner.py", "star_schema_v1_delta_runner.py",
    "star_schema_v1_preview.py", "prioridade_roubos_furtos_v1.py",
    "ml_catalogo_perfis_v3.py", "ml_perfis_territoriais_v2.py",
    "catalogo_perfis_v3_config.json", "distritos_centroides_ibge_2022.json",
)
for name in REQUIRED:
    assert (BUNDLE / name).is_file(), f"Ausente no Bundle: {name}"

spec = importlib.util.spec_from_file_location(
    "bairroiq_frontend_v1_readonly", str(BUNDLE / "frontend_v1_runner.py")
)
frontend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frontend)
result = frontend.run_from_spark(spark)
summary, visual, tech = result["resumo"], result["visual"], result["tecnico"]

VISUAL = ["Distrito", "Empregos", "Roubos", "Segurança", "Mobilidade", "Cluster"]
assert visual.shape == (96, 6)
assert list(visual.columns) == VISUAL == list(frontend.VISUAL_COLUMNS)
assert tech.shape == (96, 13)
assert tech["cd_dist"].nunique() == 96
assert tech["perfil_id"].nunique() == 9
assert summary["distritos"] == 96 and summary["clusters"] == 9
assert summary["colunas_visuais"] == 6
assert summary["escrita_executada"] is False
assert summary["publicacao_autorizada"] is False

print("BAIRROIQ | FRONTEND V1 | SEIS COLUNAS | SOMENTE LEITURA")
print(json.dumps(summary, ensure_ascii=False, indent=2))
print("\nTABELA VISUAL")
display(visual)
print("\nCAMPOS TECNICOS (12 EXEMPLOS)")
display(tech.head(12))
print("BAIRROIQ_FRONTEND_V1_SIX_COLUMNS_VALIDATED")
```

O preflight Delta `check(spark)` confirma a integridade das sete tabelas, lê apenas os dados necessários ao consumidor, não extrai a coluna LED e não escreve em nenhuma tabela. A Gold original continua preservada.
