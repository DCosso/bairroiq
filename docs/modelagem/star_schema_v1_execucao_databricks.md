# BairroIQ — Execução da prévia do Star Schema v1 no Databricks

**Pré-requisitos:** PR integrado na `main`, Databricks CD de novo módulo concluído, cópia de `star_schema_v1_preview.py` presente no diretório do bundle, acesso somente de leitura à Gold. NÃO cria tabelas Delta.

## Notebook Python: célula única

```python
from pathlib import Path
import importlib.util
import json

BUNDLE = Path(
    "/Workspace/Users/42be9e1b-1ab5-4a46-96a7-0a4691c31b5d/"
    ".bundle/barrioiq_pipeline/dev/files"
)
ARQUIVOS = [
    "star_schema_v1_preview.py", "prioridade_roubos_furtos_v1.py",
    "ml_catalogo_perfis_v3.py", "ml_perfis_territoriais_v2.py",
    "catalogo_perfis_v3_config.json", "distritos_centroides_ibge_2022.json",
]
for arquivo in ARQUIVOS:
    caminho = BUNDLE / arquivo
    if not caminho.is_file():
        raise FileNotFoundError(f"Ausente no Bundle: {caminho}")

spec = importlib.util.spec_from_file_location(
    "bairroiq_star_schema_v1_preview", str(BUNDLE / "star_schema_v1_preview.py")
)
star = importlib.util.module_from_spec(spec)
spec.loader.exec_module(star)

resultado = star.run_from_spark(spark)
resumo = resultado["resumo"]
print("=" * 65)
print("BAIRROIQ | STAR SCHEMA V1 | SOMENTE LEITURA")
print("=" * 65)
print(json.dumps(resumo, ensure_ascii=False, indent=2))

esperado = {
    "dim_snapshot": 1, "dim_distrito": 96,
    "dim_perfil": 9, "dim_indicador": 11,
    "fato_distrito_indicador": 1056,
    "fato_distrito_perfil": 96,
    "fato_prioridade_ocorrencias": 96,
}
assert resumo["linhas"] == esperado
assert resumo["alteracoes_gold"] == "NENHUMA"
assert resumo["publicacao_gold_autorizada"] is False
assert resumo["auditoria_p04_condicao_editorial"] is True
assert resumo["auditoria_p04_nome_homologado"] is False

print("\nDIMENSOES E FATOS")
for nome, quadro in resultado["tabelas"].items():
    print(f"{nome}: {len(quadro)} linhas")
    display(quadro.head(5))

print("BAIRROIQ_STAR_SCHEMA_V1_PREVIEW_VALIDATED")
```

## Exportação local (somente se for necessário compartilhar o diagnóstico)

```python
star.export_local(resultado, "/tmp/bairroiq_star_schema_v1_preview")
```

Essa exportação cria sete CSVs e um JSON em `/tmp` no driver. Não executa Spark write, não materializa views e não publica dados. O usuário deve conferir e evitar tratar resultados como homologados.

## Falhas esperadas e conduta

- `BAIRROIQ_STAR_V1_BLOCKED`: cardinalidade, FKs, perfis, hash, rank, estados ou medidas fora de contrato. **Não** trocar o hash manualmente para contornar.
- `BAIRROIQ_CATALOGO_V3_BLOCKED`: mudança na fotografia Gold ou no K-Means v3. Exige nova revisão de modelo.
- Arquivo ausente no Bundle: conferir o workflow de deploy, e não apontar o notebook para cópias locais divergentes.

## O que validar em seguida

Depois de observar as sete contagens e conferir as amostras, fazer PR separado de modelagem física: nomes no catalogo `workspace.gold` (ou schema consumer definido), permissões, invariantes de integridade, política de atualização e histórico. Enquanto a temporalidade da origem não for definida, **não** criar uma fato por período usando simplesmente a data de execução como se fosse o período dos indicadores.
