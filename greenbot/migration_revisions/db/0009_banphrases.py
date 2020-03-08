def up(cursor, bot):
    cursor.execute(
        """ALTER TABLE "banphrase" DROP COLUMN permanent"""
    )
    cursor.execute(
        """ALTER TABLE "banphrase" DROP COLUMN warning"""
    )
    cursor.execute(
        """ALTER TABLE "banphrase" DROP COLUMN notify"""
    )
    cursor.execute(
        """ALTER TABLE "banphrase" DROP COLUMN sub_immunitys"""
    )
