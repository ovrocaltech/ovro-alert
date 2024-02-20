from pydantic import BaseModel
import sqlite3
import logging

logger = logging.getLogger(__name__)

DBPATH = '/Users/claw/code/relay.db'

class Command(BaseModel):
    instrument: str
    command: str
    command_mjd: float
    args: str

def connection_factory():
    """Create a connection to the database."""
    return sqlite3.connect(DBPATH)


def create_db():
    """Create database if it doesn't exist."""
    with connection_factory() as conn:
        c = conn.cursor()
        c.executescript('''
            CREATE TABLE IF NOT EXISTS commands
            (id INTEGER PRIMARY KEY,
                instrument TEXT,
                command TEXT,
                command_mjd REAL,
                args TEXT);
            ''')


def reset_table(table='commands'):
    """Reset the sessions table."""
    with connection_factory() as conn:
        c = conn.cursor()
        c.execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()
        create_db()


def get_command(instrument: str):
    """Get the current command for an instrument."""
    with connection_factory() as conn:
        c = conn.cursor()
        c.execute('SELECT instrument, command, command_mjd, args FROM commands WHERE instrument = ?', (instrument,))
        row = c.fetchone()
        if row is None:
            return None
        instrument, command, command_mjd, args = row
        return Command(instrument=instrument, command=command, command_mjd=command_mjd, args=args)


def set_command(command: Command):
    """Set the current command for an instrument."""
    with connection_factory() as conn:
        c = conn.cursor()
        c.execute('INSERT INTO commands (instrument, command, command_mjd, args) VALUES (?, ?, ?, ?)',
                  (command.instrument, command.command, command.command_mjd, str(command.args)))
        conn.commit()
        logger.info(f"Set {command.instrument} command: {command.command} with {command.args}")
        return f"Set {command.instrument} command: {command.command} with {command.args}"


def get_commands():
    """Get the current commands for all instruments."""

    commands = []
    with connection_factory() as conn:
        c = conn.cursor()
        c.execute('SELECT instrument, command, command_mjd, args FROM commands')
        rows = c.fetchall()
        for row in rows:
            instrument, command, command_mjd, args = row
            commands.append(Command(instrument=instrument, command=command, command_mjd=command_mjd, args=args))

    return commands
