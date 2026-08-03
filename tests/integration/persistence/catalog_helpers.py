from sqlalchemy import inspect, text


def revision(mssql_database: object) -> str:
    with mssql_database.engine.connect() as connection:
        return str(connection.scalar(text("SELECT version_num FROM dbo.alembic_version")))


def _normalized(value: object) -> object:
    if isinstance(value, dict):
        return tuple(sorted((str(key), _normalized(item)) for key, item in value.items()))
    if isinstance(value, list | tuple):
        return tuple(_normalized(item) for item in value)
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)


def table_catalog_signature(mssql_database: object, table_names: set[str]) -> object:
    inspector = inspect(mssql_database.engine)
    with mssql_database.engine.connect() as connection:
        constraints = tuple(
            sorted(
                tuple(str(value) for value in row)
                for row in connection.execute(
                    text(
                        "SELECT t.name, o.type, o.name, COALESCE(cc.definition, '') "
                        "FROM sys.objects o JOIN sys.tables t "
                        "ON o.parent_object_id = t.object_id JOIN sys.schemas s "
                        "ON t.schema_id = s.schema_id LEFT JOIN sys.check_constraints cc "
                        "ON o.object_id = cc.object_id WHERE s.name = 'trading' "
                        "AND o.type IN ('PK', 'UQ', 'C')"
                    )
                ).tuples()
                if str(row[0]) in table_names
            )
        )
    reflected = tuple(
        (
            table_name,
            _normalized(inspector.get_columns(table_name, schema="trading")),
            _normalized(inspector.get_pk_constraint(table_name, schema="trading")),
            _normalized(inspector.get_foreign_keys(table_name, schema="trading")),
            _normalized(inspector.get_indexes(table_name, schema="trading")),
        )
        for table_name in sorted(table_names)
    )
    return reflected, constraints
