def up(cursor, bot):
    cursor.execute('ALTER TABLE "user" ADD COLUMN user_name TEXT NOT NULL')