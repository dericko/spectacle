import psycopg


class ArtifactMetadataStore:
    def __init__(self, conn_string: str) -> None:
        self.conn_string = conn_string

    def setup(self) -> None:
        with psycopg.connect(self.conn_string) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS artifacts (
                    id SERIAL PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    scene_id TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
            conn.commit()

    def record(self, run_id: str, content_hash: str, stage: str, scene_id: str | None) -> None:
        with psycopg.connect(self.conn_string) as conn:
            conn.execute(
                "INSERT INTO artifacts (run_id, content_hash, stage, scene_id) VALUES (%s, %s, %s, %s)",
                (run_id, content_hash, stage, scene_id),
            )
            conn.commit()

    def list_for_run(self, run_id: str) -> list[dict]:
        with psycopg.connect(self.conn_string) as conn:
            rows = conn.execute(
                "SELECT content_hash, stage, scene_id, created_at FROM artifacts "
                "WHERE run_id = %s ORDER BY created_at ASC",
                (run_id,),
            ).fetchall()
            columns = ["content_hash", "stage", "scene_id", "created_at"]
            return [dict(zip(columns, row)) for row in rows]
