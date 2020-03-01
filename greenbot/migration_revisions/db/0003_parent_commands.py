def up(cursor, bot):
    cursor.execute(
        """ALTER TABLE "command" ADD COLUMN parent_command TEXT DEFAULT NULL """
    )
