def up(cursor, bot):
    cursor.execute(
        """
    CREATE TABLE "user" (
        discord_id TEXT PRIMARY KEY NOT NULL,
        points INT NOT NULL DEFAULT 0
    )
    """
    )
    
    cursor.execute(
        """
    CREATE TABLE "message" (
        message_id TEXT PRIMARY KEY NOT NULL,   
        user_id TEXT NOT NULL REFERENCES "user"(discord_id),
        channel_id TEXT,
        content TEXT NOT NULL,
        time_sent timestamp with time zone
    )
    """
    )

    cursor.execute(
        """
    CREATE TABLE command (
        id INT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        level INT NOT NULL,
        action TEXT DEFAULT NULL,
        extra_args TEXT DEFAULT NULL,
        command TEXT NOT NULL,
        description TEXT DEFAULT NULL,
        delay_all INT NOT NULL,
        delay_user INT NOT NULL,
        enabled BOOLEAN NOT NULL,
        cost INT NOT NULL,
        can_execute_with_whisper BOOLEAN DEFAULT NULL,
    )
    """
    )

    cursor.execute(
        """
    CREATE TABLE command_data (
        command_id INT PRIMARY KEY NOT NULL REFERENCES "command"(id),
        num_uses INT NOT NULL,
        added_by TEXT DEFAULT NULL,
        edited_by TEXT DEFAULT NULL,
        last_date_used TIMESTAMPTZ DEFAULT NULL
    )
    """
    )

    cursor.execute(
        """
    CREATE TABLE command_example (
        id INT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        command_id INT NOT NULL REFERENCES "command"(id),
        title TEXT NOT NULL,
        chat TEXT NOT NULL,
        description TEXT NOT NULL
    )
    """
    )