def up(cursor, bot):
    cursor.execute(
        """ALTER TABLE "banphrase" DELETE COLUMN permanent"""
    )
    cursor.execute(
        """ALTER TABLE "banphrase" DELETE COLUMN warning"""
    )
    cursor.execute(
        """ALTER TABLE "banphrase" DELETE COLUMN notify"""
    )
    cursor.execute(
        """ALTER TABLE "banphrase" DELETE COLUMN sub_immunitys"""
    )
