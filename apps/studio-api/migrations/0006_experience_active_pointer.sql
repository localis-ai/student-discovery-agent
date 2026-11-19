DO $$
BEGIN
  CREATE TABLE IF NOT EXISTS product.experience_active (
    experience_id TEXT NOT NULL REFERENCES product.experiences(id),
    environment TEXT NOT NULL CHECK (environment IN ('demo', 'prod')),
    release_id TEXT NOT NULL REFERENCES product.experience_releases(id),
    revision BIGINT NOT NULL CHECK (revision >= 1),
    updated_by TEXT NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (experience_id, environment)
  );
END
$$;
