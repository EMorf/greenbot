def up(cursor, bot):
    cursor.execute(
        """ALTER TABLE command_data DROP CONSTRAINT IF EXISTS command_data_command_id_fkey;"""
    )
    cursor.execute(
        """
        ALTER TABLE command_data
            ADD CONSTRAINT command_data_command_id_fkey FOREIGN KEY (command_id)
            REFERENCES "command"(id) MATCH SIMPLE
            ON UPDATE NO ACTION
            ON DELETE CASCADE;
        """
    )
    cursor.execute(
        """ALTER TABLE command_example DROP CONSTRAINT IF EXISTS command_example_command_id_fkey;"""
    )
    cursor.execute(
        """ALTER TABLE command_example
            ADD CONSTRAINT command_example_command_id_fkey FOREIGN KEY (command_id)
            REFERENCES "command"(id) MATCH SIMPLE
            ON UPDATE NO ACTION
            ON DELETE NO ACTION;
        """
    )
    cursor.execute(
        """DELETE FROM "command" WHERE parent_command IS NOT NULL;"""
    )
    cursor.execute(
        """ALTER TABLE "command" DROP COLUMN parent_command;"""
    )
    cursor.execute(
        """ALTER TABLE "command" ADD COLUMN group TEXT;"""
    )
