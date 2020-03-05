def up(cursor, bot):
    cursor.execute(
        """
    CREATE TABLE timeouts(
        id SERIAL PRIMARY KEY,
        username TEXT
    )
    """
    )
