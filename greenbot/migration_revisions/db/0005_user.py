def up(cursor, bot):
    cursor.execute('ALTER TABLE "user" ADD COLUMN level INT NOT NULL DEFAULT 100')