# BairroIQ — Execução reprodutível v3 no Databricks

**Pré-requisitos:** PR da v3 integrado à `main`; CI e CD concluídos; arquivo `.py` e JSON efetivamente presentes no Bundle. Notebook Python no mesmo workspace da `workspace.gold.distritos_wide`. Código v3 e v2 devem estar no mesmo diretório do Bundle. Esta célula não grava tabelas.

```python
from pathlib import Path
import importlib.util
import json

BUNDLE = Path(
    '/Workspace/Users/42be9e1b-1ab5-4a46-96a7-0a4691c31b5d/'
    '.bundle/barrioiq_pipeline/dev/files'
)
SCRIPT = BUNDLE / 'ml_catalogo_perfis_v3.py'
CONFIG = BUNDLE / 'catalogo_perfis_v3_config.json'
V2 = BUNDLE / 'ml_perfis_territoriais_v2.py'
REFERENCIA = BUNDLE / 'distritos_centroides_ibge_2022.json'

for path in (SCRIPT, CONFIG, V2, REFERENCIA):
    if not path.is_file():
        raise FileNotFoundError(f'Arquivo nao publicado no Bundle: {path}')

spec = importlib.util.spec_from_file_location('bairroiq_catalogo_v3', str(SCRIPT))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

print('BAIRROIQ_CATALOGO_V3_INICIO')
resultado = mod.run_from_spark(spark)
resumo = resultado['resumo']
print('Hash:', resumo['sha256_gold'])
print('Versao:', resumo['versao'])
print('Perfis:', resumo['perfis'], 'Distritos:', resumo['distritos'])
print('Metricas:', json.dumps(resumo['metricas_reproduzidas'], ensure_ascii=False))
print('Gold alterada:', resumo['alteracoes_gold'])
print('Status:', resumo['status'])
print('Publicacao autorizada:', resumo['publicacao_gold_autorizada'])

display(resultado['catalogo'][[
    'perfil_id', 'nome_provisorio', 'qtd_distritos', 'evidencias_json',
    'silhouette_mediana', 'distritos_silhouette_negativa',
    'exemplos_distritos_json', 'ressalva_especifica'
]])
display(resultado['distritos'][[
    'CD_DIST', 'NM_DIST', 'perfil_id', 'silhouette_individual',
    'tipo_pertencimento', 'representatividade_interna_0a100'
]])

assert resumo['perfis'] == 9 and resumo['distritos'] == 96
assert resumo['publicacao_gold_autorizada'] is False
assert resumo['alteracoes_gold'] == 'NENHUMA'
print('BAIRROIQ_CATALOGO_V3_SNAPSHOT_VALIDATED')
```

### Exportar artefatos temporários (opcional)

Somente após conferir a execução, rode `mod.export(resultado, '/tmp/bairroiq_catalogo_v3')`. Isso cria **três arquivos locais**, não tabelas Delta: `catalogo_perfis_v3.csv`, `distritos_por_perfil_v3.csv`, `resumo_catalogo_v3.json`. Antes de enviar resultados ao GitHub, confirme a origem, os nomes oficiais e o status de revisão. Não confundir saída de teste sintético do CI com dado real de produção.

Se ocorrer `BAIRROIQ_CATALOGO_V3_BLOCKED`, **não contorne a validação**: compare o hash, o código v2 instalado, a composição dos nove clusters e as versões do scikit-learn. Uma mudança real exige nova revisão da fotografia de dados e dos rótulos.

## Buscar distritos com menos roubos e furtos

Após validar o catálogo v3, execute `docs/ml/execucao_prioridade_ocorrencias_v1.md`. O resultado é uma **prioridade independente dos clusters**, com auditoria condicional do nome P04; sem publicação Gold.
