import dataclasses
import logging
import os
import sqlite3

import click
import rich
from appdirs import AppDirs
from pydantic import BaseModel

logger = logging.getLogger(__name__)


def _logging(level):
    logger.setLevel(level)
    logging.basicConfig(level=level)


appdirs = AppDirs("habits_tracker")
_DATA_DIR = appdirs.user_data_dir
_DATABASE_FILE_NAME = "db.sqlite3"
_DATABASE_FILE_PATH = os.path.join(_DATA_DIR, _DATABASE_FILE_NAME)


def _filter_kwargs(data):
    result = {}
    for key, val in data.items():
        if val is not None:
            result.update({key: val})
    return result


class Model:
    _table: str
    __fields__: dict

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def from_values(cls, values):
        fields = cls.__fields__.keys()
        data = {}
        for key, val in zip(fields, values):
            data.update({key: val})
        instance = cls(**data)
        return instance


class Habit(Model, BaseModel):
    _table = "habits"
    title: str
    description: str
    required: bool
    negative: bool


_CREATE_TABLES = """
CREATE TABLE habits (
    title varchar (255) UNIQUE NOT NULL,
    description varchar (2048),
    require bool NOT NULL,
    negative bool NOT NULL,
    PRIMARY KEY (title)
);
CREATE TABLE habit_records (
    uuid varchar (255) UNIQUE NOT NULL,
    habit int NOT NULL,
    added datetime NOT NULL,
    PRIMARY_KEY (uuid),
    FOREGIN KEY (habit) REFERENCES habits(title)
);
CREATE TABLE habit_names (
    habit int NOT NULL,
    name varchar (255) UNIQUE NOT NULL,
    PRIMARY_KEY (name),
    FOREGIN KEY (habit) REFERENCES habits(title)
);
"""


def _check_dir(directory):
    logger.info("Checking database directory '%s'.", directory)
    if not os.path.exists(directory):
        os.makedirs(directory)


def _check_database(database: str) -> sqlite3.Connection:
    logger.info("Checking database file '%s'.", database)
    connection = sqlite3.connect(database)
    cursor = connection.cursor()
    tables = cursor.execute(
        """SELECT * FROM sqlite_master WHERE type='table'"""
    ).fetchall()
    if not tables:
        create_tables(connection)
    return connection


def create_tables(connection: sqlite3.Connection):
    logger.info("Creating tables.")
    cursor = connection.cursor()
    cursor.executescript(_CREATE_TABLES)
    connection.commit()


@dataclasses.dataclass
class HabitsTrackerSettings:
    connection: sqlite3.Connection
    database: str = _DATABASE_FILE_PATH
    verbose: bool = False
    debug: bool = False


@click.group()
@click.option("-d", "--database", type=str, help="Database file.")
@click.option("-v", "--verbose", is_flag=True)
@click.option("--debug", is_flag=True)
@click.pass_context
def commands(context, **kwargs):
    if kwargs["verbose"] or kwargs["debug"]:
        if kwargs["debug"]:
            level = logging.DEBUG
        else:
            level = logging.INFO
        _logging(level)
        logging.info("kwargs: '%s'", kwargs)
    db = kwargs["database"]
    if not db:
        _check_dir(_DATA_DIR)
        connection = _check_database(_DATABASE_FILE_PATH)
    else:
        connection = _check_database(db)
    context.obj = HabitsTrackerSettings(
            **_filter_kwargs(kwargs),
            connection=connection)


@commands.command("add")
@click.option("--title", type=str, prompt=True)
@click.option("--description", type=str, default="", prompt=True)
@click.option("--require", type=bool, default=False, prompt=True)
@click.option("--negative", type=bool, default=False, prompt=True)
@click.pass_context
def habit_add(context, **kwargs):
    logger.debug("Adding habit: '%s'", kwargs)
    con = context.obj.connection
    cur = con.cursor()
    fields = ", ".join([str(x) for x in kwargs.keys()])
    values = ", ".join([f'"{x}"' for x in kwargs.values()])
    insert = f"INSERT INTO habits ({fields}) VALUES ({values});"
    logger.debug(insert)
    cur.execute(insert)
    con.commit()
    return


@commands.command("list")
@click.pass_context
def habits_list(context):
    con = context.obj.connection
    cur = con.cursor()
    habits_data = cur.execute("SELECT * FROM habits;").fetchall()
    habits = [Habit.from_values(data) for data in habits_data]
    rich.print(habits)


@commands.command("exec")
@click.argument("command", type=str)
@click.pass_context
def exec_sql(context, command):
    con = context.obj.connection
    cur = con.cursor()
    result = cur.execute(command).fetchall()
    if result:
        rich.print(result)


def main():
    commands()


if __name__ == "__main__":
    main()
