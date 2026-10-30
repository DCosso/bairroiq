
-- BairroIQ | Bronze | IBGE
-- Agregados básicos por distrito
-- Indicadores preservados como STRING na Bronze.

CREATE TABLE IF NOT EXISTS
workspace.bronze.ibge_agregados_basico_distritos (
    CD_DIST INT,
    NM_DIST STRING COLLATE UTF8_BINARY,
    CD_REGIAO INT,
    NM_REGIAO STRING COLLATE UTF8_BINARY,
    CD_UF INT,
    NM_UF STRING COLLATE UTF8_BINARY,
    CD_MUN INT,
    NM_MUN STRING COLLATE UTF8_BINARY,
    CD_NU STRING COLLATE UTF8_BINARY,
    NM_NU STRING COLLATE UTF8_BINARY,
    CD_AGLOM STRING COLLATE UTF8_BINARY,
    NM_AGLOM STRING COLLATE UTF8_BINARY,
    CD_RGINT INT,
    NM_RGINT STRING COLLATE UTF8_BINARY,
    CD_RGI INT,
    NM_RGI STRING COLLATE UTF8_BINARY,
    CD_CONCURB STRING COLLATE UTF8_BINARY,
    NM_CONCURB STRING COLLATE UTF8_BINARY,
    AREA_KM2 STRING COLLATE UTF8_BINARY,

    domicilios_particulares_permanentes_ou_pessoas_responsaveis
        STRING COLLATE UTF8_BINARY,

    moradores_domicilios_particulares_permanentes_ou_populacao_residente
        STRING COLLATE UTF8_BINARY,

    media_moradores_domicilios_particulares_permanentes
        STRING COLLATE UTF8_BINARY,

    variancia_numero_moradores_domicilios_particulares_permanentes
        STRING COLLATE UTF8_BINARY,

    rendimento_nominal_medio_mensal_responsaveis_com_sem_rendimento
        STRING COLLATE UTF8_BINARY,

    variancia_rendimento_nominal_mensal_responsaveis_com_sem_rendimento
        STRING COLLATE UTF8_BINARY,

    rendimento_nominal_medio_mensal_responsaveis_com_rendimento
        STRING COLLATE UTF8_BINARY,

    variancia_rendimento_nominal_mensal_responsaveis_com_rendimento
        STRING COLLATE UTF8_BINARY,

    rendimento_nominal_medio_mensal_pessoas_10_anos_ou_mais_com_sem_rendimento
        STRING COLLATE UTF8_BINARY
)
USING DELTA
CLUSTER BY AUTO;
