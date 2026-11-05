# BairroIQ | Validação no Databricks: prioridade "Menos roubos e furtos"

**Pré-requisito:** importar os arquivos desta revisão na branch v3; aprovar o PR, integrar à `main`, concluir CD. Apenas leitura da Gold de 96 distritos. Código usa catálogo v3 e v2 versionados.

Notebook Python:

```python
from pathlib import Path
import importlib.util
import json

BUNDLE = Path(
    '/Workspace/Users/42be9e1b-1ab5-4a46-96a7-0a4691c31b5d/'
    '.bundle/barrioiq_pipeline/dev/files'
)
SCRIPT = BUNDLE / 'prioridade_roubos_furtos_v1.py'
if not SCRIPT.is_file():
    raise FileNotFoundError(f'Modulo de prioridades nao publicado: {SCRIPT}')

spec = importlib.util.spec_from_file_location('bairroiq_prioridade_ocorrencias', str(SCRIPT))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

resultados = mod.run_from_spark(spark)  # Gold real, 96 linhas, somente leitura
print('BAIRROIQ | PRIORIDADE OCORRENCIAS | DADOS REAIS')
print('Hash da Gold:', resultados['resumo']['sha256_gold'])
print('Status:', resultados['resumo']['status'])
print('Aprovado para Gold:', resultados['resumo']['publicacao_gold_autorizada'])
print('AUDITORIA DO NOME P04:')
print(json.dumps(resultados['auditoria_p04'], ensure_ascii=False, indent=2))
print('CATALOGO DE PERFIS (NOMES CONDICIONAIS):')
display(resultados['catalogo'][['perfil_id','nome_provisorio','nome_exibicao_proposto', 'nome_validado_para_publicacao']])
print('20 DISTRITOS COM MENORES TAXAS COMBINADAS:')
display(mod.filter_priority(resultados, limit=20)[[
    'CD_DIST','NM_DIST','perfil_id','roubos','furtos',
    'percentil_relativo_roubos_0a100','percentil_relativo_furtos_0a100',
    'posicao_relativa_entre_96',
]])
print('EXEMPLO: PRIORIZAR DENTRO DO PERFIL P04:')
display(mod.filter_priority(resultados, perfil_id='kmeans-k09-p04', limit=10)[[
    'NM_DIST','roubos','furtos','posicao_relativa_entre_96',
]])
print('GOLD ALTERADA:', resultados['resumo']['alteracoes_gold'])
print('BAIRROIQ_OCORRENCIAS_PRIORITY_EXPLORATORY_SUCCESS')
```

Salvar as três tabelas de auditoria como CSV ou encaminhar outputs para revisão. Não usar automaticamente o nome condicional P04 no site; `nome_validado_para_publicacao=False` exige conferência humana.
