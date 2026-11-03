
-- ============================================================
-- BairroIQ | Silver | IBGE - Censo Demografico 2022
-- ============================================================
-- Fonte:
--   workspace.bronze.ibge_agregados_basico_v2
--
-- Destino:
--   workspace.silver.ibge_agregados_basicos_v2
--
-- Recorte geografico:
--   Municipio de Sao Paulo (IBGE 3550308)
--
-- Objetivo:
--   Tipagem e padronizacao dos agregados basicos por distrito.
--
-- Referencia:
--   Dicionario IBGE - 20/05/2026
--
-- ATENCAO:
--   CREATE OR REPLACE substitui o conteudo da tabela destino.
--   Este arquivo esta sendo apenas versionado nesta etapa.
--   Nao executar antes de integrar as validacoes ao pipeline.
-- ============================================================

CREATE OR REPLACE TABLE
    workspace.silver.ibge_agregados_basicos_v2

USING DELTA

AS

SELECT

    -- ========================================================
    -- Identificacao territorial
    -- ========================================================

    CD_DIST,
    NM_DIST,
    CD_MUN,
    NM_MUN,

    -- ========================================================
    -- Area territorial (km2)
    -- ========================================================

    TRY_CAST(
        REPLACE(
            NULLIF(TRIM(AREA_KM2), '.'),
            ',',
            '.'
        ) AS DECIMAL(18, 8)
    ) AS area_km2,

    -- ========================================================
    -- Populacao e domicilios
    -- ========================================================

    -- V0001: Total de pessoas
    TRY_CAST(
        NULLIF(TRIM(V0001), '.')
        AS BIGINT
    ) AS total_pessoas,

    -- V0002: Total de domicilios
    TRY_CAST(
        NULLIF(TRIM(V0002), '.')
        AS BIGINT
    ) AS total_domicilios,

    -- V0003: Total de domicilios particulares
    TRY_CAST(
        NULLIF(TRIM(V0003), '.')
        AS BIGINT
    ) AS total_domicilios_particulares,

    -- V0004: Total de domicilios coletivos
    TRY_CAST(
        NULLIF(TRIM(V0004), '.')
        AS BIGINT
    ) AS total_domicilios_coletivos,

    -- V0005: Media de moradores em domicilios
    -- particulares ocupados
    TRY_CAST(
        REPLACE(
            NULLIF(TRIM(V0005), '.'),
            ',',
            '.'
        ) AS DECIMAL(10, 4)
    ) AS media_moradores_domicilios_ocupados,

    -- V0006: Proporcao de domicilios particulares
    -- ocupados imputados, expressa em percentual
    TRY_CAST(
        REPLACE(
            NULLIF(TRIM(V0006), '.'),
            ',',
            '.'
        ) AS DECIMAL(10, 6)
    ) * 100 AS percentual_domicilios_ocupados_imputados,

    -- V0007: Domicilios particulares ocupados
    TRY_CAST(
        NULLIF(TRIM(V0007), '.')
        AS BIGINT
    ) AS total_domicilios_particulares_ocupados,

    -- V0008: Domicilios particulares de uso ocasional
    TRY_CAST(
        NULLIF(TRIM(V0008), '.')
        AS BIGINT
    ) AS total_domicilios_uso_ocasional,

    -- V0009: Domicilios particulares permanentes vagos
    TRY_CAST(
        NULLIF(TRIM(V0009), '.')
        AS BIGINT
    ) AS total_domicilios_permanentes_vagos

FROM
    workspace.bronze.ibge_agregados_basico_v2

WHERE
    CD_MUN = '3550308';
