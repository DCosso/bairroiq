-- BairroIQ | Consultas de auditoria da tabela V2
-- Executar SOMENTE APÓS materialização autorizada da tabela interna.
-- Não modifica dados, acessos ou flags.

-- 1) Conferência global dos 96 distritos e da trilha de auditoria
SELECT
    COUNT(*) AS linhas,
    COUNT(DISTINCT cd_dist) AS distritos_distintos,
    COUNT(DISTINCT neighborhood) AS nomes_distintos,
    COUNT(DISTINCT perfil_id) AS perfis_distintos,
    COUNT(DISTINCT snapshot_id) AS snapshots,
    COUNT(DISTINCT versao_contrato) AS versoes_contrato,
    COUNT(DISTINCT payload_sha256) AS hashes_payload,
    COUNT(DISTINCT sql_sha256) AS hashes_sql,
    SUM(CASE WHEN publicacao_autorizada = FALSE THEN 1 ELSE 0 END) AS linhas_nao_publicaveis,
    SUM(CASE WHEN
        snapshot_id IS NULL OR cd_dist IS NULL OR neighborhood IS NULL OR
        latitude IS NULL OR longitude IS NULL OR
        formal_jobs_score IS NULL OR safety_score IS NULL OR mobility_score IS NULL OR
        green_leisure_score IS NULL OR public_services_score IS NULL OR
        densidade_hab_km2 IS NULL OR robberies_per_1000 IS NULL OR
        perfil_id IS NULL OR cluster IS NULL OR tipo_territorio IS NULL OR
        publicacao_autorizada IS NULL OR versao_contrato IS NULL OR
        payload_sha256 IS NULL OR sql_sha256 IS NULL OR materializado_em_utc IS NULL
        THEN 1 ELSE 0 END) AS linhas_com_campo_nulo,
    MIN(materializado_em_utc) AS materializado_em_utc,
    MIN(payload_sha256) AS payload_sha256,
    MIN(sql_sha256) AS sql_sha256
FROM workspace.gold.bairroiq_frontend_v2;

-- 2) Distribuição do ML (esperada 9,7,6,22,7,8,12,19,6)
SELECT
    perfil_id,
    cluster,
    COUNT(*) AS distritos
FROM workspace.gold.bairroiq_frontend_v2
GROUP BY perfil_id, cluster
ORDER BY perfil_id;

-- 3) Dados exatamente no contrato de consumo (16 campos)
SELECT
    snapshot_id,
    cd_dist,
    neighborhood,
    latitude,
    longitude,
    formal_jobs_score,
    safety_score,
    mobility_score,
    green_leisure_score,
    public_services_score,
    densidade_hab_km2,
    robberies_per_1000,
    perfil_id,
    cluster,
    tipo_territorio,
    publicacao_autorizada
FROM workspace.gold.bairroiq_frontend_v2
ORDER BY cd_dist;
