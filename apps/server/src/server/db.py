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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'running',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
            conn.commit()

    def create_run(self, run_id: str, name: str) -> None:
        with psycopg.connect(self.conn_string) as conn:
            conn.execute(
                "INSERT INTO runs (run_id, name) VALUES (%s, %s)",
                (run_id, name),
            )
            conn.commit()

    def update_run_status(self, run_id: str, status: str) -> None:
        with psycopg.connect(self.conn_string) as conn:
            conn.execute(
                "UPDATE runs SET status = %s WHERE run_id = %s",
                (status, run_id),
            )
            conn.commit()

    def list_runs(self) -> list[dict]:
        with psycopg.connect(self.conn_string) as conn:
            rows = conn.execute(
                "SELECT run_id, name, status, created_at FROM runs ORDER BY created_at DESC"
            ).fetchall()
            columns = ["run_id", "name", "status", "created_at"]
            return [dict(zip(columns, row)) for row in rows]

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
