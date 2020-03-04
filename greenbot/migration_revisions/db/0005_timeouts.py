def up(cursor, bot):
    cursor.execute(
        """ALTER TABLE "timeouts" ADD COLUMN unbanned_at TIMESTAMPTZ"
    )"""
    )
