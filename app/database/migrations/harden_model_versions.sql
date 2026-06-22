ALTER TABLE model_versions
ADD COLUMN IF NOT EXISTS feature_schema_hash VARCHAR(64),
    ADD COLUMN IF NOT EXISTS training_data_hash VARCHAR(64),
    ADD COLUMN IF NOT EXISTS physics_version VARCHAR(50);
