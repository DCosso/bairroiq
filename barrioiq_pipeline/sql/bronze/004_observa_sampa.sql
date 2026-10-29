
-- BairroIQ | Bronze | ObservaSampa

CREATE TABLE IF NOT EXISTS workspace.bronze.observa_sampa (
    Nome           STRING COLLATE UTF8_BINARY,
    `Região`       STRING COLLATE UTF8_BINARY,
    `Período`      INT,
    Resultado      STRING COLLATE UTF8_BINARY,
    _rescued_data  STRING COLLATE UTF8_BINARY
)
USING DELTA
COMMENT 'Indicadores do ObservaSampa por nome, regiao e periodo.'
CLUSTER BY AUTO;
