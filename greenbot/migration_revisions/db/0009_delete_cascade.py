def up(cursor, bot):
    cursor.execute("""
        ALTER TABLE message DROP CONSTRAINT message_user_id_fkey;
    """)

    cursor.execute("""
    ALTER TABLE message 
    ADD CONSTRAINT message_user_id_fkey 
    FOREIGN KEY (user_id) 
    REFERENCES "user"(discord_id) 
    ON DELETE CASCADE;
    """)
