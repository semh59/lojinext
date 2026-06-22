CREATE TABLE IF NOT EXISTS model_versions (
    id SERIAL PRIMARY KEY,
    arac_id INTEGER REFERENCES araclar(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    model_type VARCHAR(50) NOT NULL,
    params_json TEXT NOT NULL,
    r2_score FLOAT,
    mae FLOAT,
    sample_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_model_versions_arac_id ON model_versions(arac_id);
