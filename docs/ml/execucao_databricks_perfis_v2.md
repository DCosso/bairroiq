# Execução do ML v2 na Gold real — Databricks

**Pré-requisito:** PR da v2 aprovado e integrado à `main`, CI completo, CD concluído. Não rodar a versão do ZIP como script independente sem as referências oficiais já existentes no Bundle. O código da v2 não executa nenhuma gravação de tabela.

Em um notebook **Python** do workspace, executar uma única célula, ajustando `BUNDLE` caso o local de deploy tenha mudado:

```python
from pathlib import Path
import importlib.util
import json

BUNDLE = Path(
    '/Workspace/Users/42be9e1b-1ab5-4a46-96a7-0a4691c31b5d/'
    '.bundle/barrioiq_pipeline/dev/files'
)
SCRIPT = BUNDLE / 'ml_perfis_territoriais_v2.py'
REFERENCE = BUNDLE / 'distritos_centroides_ibge_2022.json'

if not SCRIPT.is_file():
    raise FileNotFoundError(f'Arquivo v2 nao publicado: {SCRIPT}')
if not REFERENCE.is_file():
    raise FileNotFoundError(f'Referencia IBGE nao publicada: {REFERENCE}')

spec = importlib.util.spec_from_file_location('bairroiq_ml_perfis_v2', str(SCRIPT))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

print('BAIRROIQ_ML_V2_INICIO')
resultado = mod.run_from_spark(spark)  # somente leitura, 96 distritos
print('RESULTADO REAL NA GOLD:', json.dumps(resultado['resumo'],
                                           ensure_ascii=False, indent=2))
print('METRICAS:')
display(resultado['metricas'])
print('FICHAS DOS PERFIS:')
display(resultado['perfis'])
print('DISTRITOS POR PERFIL:')
display(resultado['atribuicoes'])
print('TABELAS GOLD ALTERADAS: NENHUMA')
print('BAIRROIQ_ML_V2_EXPLORATORY_SUCCESS')
```

Resultados a registrar no GitHub em uma **segunda PR, após execução**: 22 métricas, 6 cenários de produto, comparação de K=8/9/10, tamanho do menor cluster, nomes provisórios, aprovação/reprovação dos guardrails, hash SHA256 e versões das bibliotecas. Se a Gold mudar, o hash também deve mudar e precisa ser investigado. Não preencher documentação com resultados sintéticos dos testes unitários.

Para exportar artefatos temporários locais (opcional, sem Delta): `mod.export(resultado, '/tmp/bairroiq_ml_perfis_v2')`. Publicar relatórios versionados só depois de verificar que a fonte e as versões são as mesmas da execução documentada.
