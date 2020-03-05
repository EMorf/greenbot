def up(cursor, bot):
    cursor.execute(
        """
    CREATE TABLE twitter_following(
        id SERIAL PRIMARY KEY,
        username TEXT
    )
    """
    )
