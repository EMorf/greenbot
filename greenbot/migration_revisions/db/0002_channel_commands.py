def up(cursor, bot):
    cursor.execute(
        """ALTER TABLE "command" ADD COLUMN channels TEXT NOT NULL DEFAULT '[]'"""
    )
