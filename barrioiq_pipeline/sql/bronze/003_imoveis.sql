
-- BairroIQ | Bronze | Indicadores imobiliários

CREATE TABLE IF NOT EXISTS workspace.bronze.imoveis (
    mes                        DATE,
    bairro                     STRING COLLATE UTF8_BINARY,
    transacao                  STRING COLLATE UTF8_BINARY,
    mediana_m2                 INT,
    p25_m2                     INT,
    p75_m2                     INT,
    anuncios_ativos_media_dia  INT,
    novos_anuncios             INT,
    dias_no_mercado_medio      INT,
    _rescued_data              STRING COLLATE UTF8_BINARY
)
USING DELTA
CLUSTER BY AUTO;
