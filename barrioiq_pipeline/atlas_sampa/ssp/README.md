# Atlas Sampa | Coleta SSP-SP V1

Implementação inicial do **coletor versionado do Excel da SSP-SP**. Não é ainda a arquitetura Lambda completa; trata apenas a etapa de obtenção da fonte, validação do contrato e preservação da versão em Raw.

## Contrato

- Origem: arquivo `SPDadosCriminais_{ano}.xlsx` no endereço oficial `https://www.ssp.sp.gov.br/assets/estatistica/transparencia/spDados/`.
- Para 2026: abas obrigatórias `JAN-JUN_2026` e `JUL-DEZ_2026`, 30 colunas de origem, incluindo `COD IBGE` com espaço.
- O arquivo pode declarar colunas extras completamente vazias; qualquer valor não vazio em colunas adicionais bloqueia a coleta.
- SHA-256 do conteúdo baixado identifica uma **versão do arquivo**, não a identidade de cada ocorrência policial.
- `ETag` e `Last-Modified` são metadados auxiliares; não substituem o SHA-256.
- A conferência de linhas é feita em leitura sequencial, sem DataFrame em memória.
- O processo não transforma nem elimina registros da fonte.

## Uso

Ambiente com Python 3.12 e `openpyxl==3.1.5`:

```bash
cd barrioiq_pipeline
python -m pip install -r atlas_sampa/ssp/requirements.txt
python -m atlas_sampa.ssp.collector --year 2026 --check
python -m atlas_sampa.ssp.collector --year 2026 --apply
```

`--check` só consulta HEAD e não grava. `--apply` baixa a publicação inteira e compara SHA-256 com as versões já persistidas. Se o mesmo hash existir, valida sua integridade e não o sobrescreve.

- Raw padrão: `/Volumes/workspace/bronze/raw/ssp/`
- Versões: `versions/{ano}/{sha256}.xlsx` e `{sha256}.json`
- O arquivo histórico `SPDadosCriminais_2026.xlsx` na raiz permanece intocado.
- A versão SSP de 2026 anteriormente obtida manualmente permanece preservada, inclusive seus metadados.
- Não versionar no Git os arquivos de dados nem dados policiais de linha.

## Testes

```bash
python -m unittest discover -s ../tests -p 'test_atlas_sampa_ssp_collector.py' -v
```

Os testes são offline com Excel sintético e não consultam a fonte oficial nem escrevem no Databricks. O workflow `atlas-sampa-ssp-collector-ci.yml` instala a dependência fixada para executá-los.

## Limites e próximas fases

- **Ainda não agendado**. O futuro Job será mensal no dia **10, às 10h, `America/Sao_Paulo`**, e permanecerá pausado até homologação integral.
- **Ainda não executa ingestão Delta Bronze/Silver**, deduplicação, reconciliação de versões, speed/batch ou serving.
- O nome do produto é Atlas Sampa; BairroIQ é o identificador técnico do repositório.
- O tratamento de mudanças no layout da fonte e a transição de 2026 para 2027 devem ser testados antes de operar no novo ano. O coletor falha de forma explícita se o contrato esperado mudar.
- **Não rodar simultaneamente duas instâncias `--apply`**. O futuro Job declarará `max_concurrent_runs: 1`. O código não implementa lock distribuído.
- `os.replace` é usado para promover uma cópia validada no Volume. O comportamento será homologado no workspace antes de ativar o Job.
- Os dados da SSP podem ser sensíveis; logs não devem divulgar identificadores de BO, endereços ou dados de linhas.
