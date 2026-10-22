
CREATE TABLE IF NOT EXISTS
workspace.observability.data_quality_runs (
    run_id STRING NOT NULL,
    executed_at TIMESTAMP NOT NULL,
    pipeline STRING NOT NULL,
    status STRING NOT NULL,

    bronze_records BIGINT,
    bronze_missing_keys BIGINT,
    bronze_duplicate_keys BIGINT,

    silver_records BIGINT,
    gold_districts BIGINT,

    silver_population BIGINT,
    gold_population BIGINT,

    duration_seconds DOUBLE,
    error_message STRING
)
USING DELTA
COMMENT 'Historico de qualidade dos pipelines BarrioIQ';
