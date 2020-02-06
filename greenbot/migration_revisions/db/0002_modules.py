def up(cursor, bot):
    cursor.execute("""
    CREATE TABLE "module" (
        id TEXT PRIMARY KEY NOT NULL,   
        enabled BOOLEAN NOT NULL DEFAULT FALSE,
        settings TEXT
    )
    """)