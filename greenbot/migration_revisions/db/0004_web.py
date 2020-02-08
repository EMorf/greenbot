def up(cursor, bot):
    cursor.execute("""
    CREATE TABLE "command_example" (
        id TEXT PRIMARY KEY NOT NULL,   
        command_id INT NOT NULL REFERENCES "command"(id),
        title TEXT NOT NULL,
        chat TEXT NOT NULL,
        description TEXT NOT NULL
    )
    """)
    cursor.execute(
        """
    CREATE TABLE banphrase (
        id INT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        name TEXT NOT NULL,
        phrase TEXT NOT NULL,
        length INT NOT NULL,
        permanent BOOLEAN NOT NULL,
        warning BOOLEAN NOT NULL,
        notify BOOLEAN NOT NULL,
        case_sensitive BOOLEAN NOT NULL,
        enabled BOOLEAN NOT NULL,
        operator TEXT NOT NULL DEFAULT 'contains',
        sub_immunity BOOLEAN NOT NULL DEFAULT FALSE,
        remove_accents BOOLEAN NOT NULL
    )
    """
    )

    cursor.execute(
        """
    CREATE TABLE banphrase_data (
        banphrase_id INT PRIMARY KEY NOT NULL REFERENCES banphrase(id),
        num_uses INT NOT NULL,
        added_by INT DEFAULT NULL,
        edited_by INT DEFAULT NULL
    )
    """
    )
    cursor.execute(
        """
    CREATE TABLE timer (
        id INT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        name TEXT NOT NULL,
        action TEXT NOT NULL,
        interval_online INT NOT NULL,
        interval_offline INT NOT NULL,
        enabled BOOLEAN NOT NULL
    )
    """
    )