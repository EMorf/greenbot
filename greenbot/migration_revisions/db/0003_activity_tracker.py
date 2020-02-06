def up(cursor, bot):
    cursor.execute('ALTER TABLE "message" ADD COLUMN credited BOOLEAN NOT NULL DEFAULT FALSE')