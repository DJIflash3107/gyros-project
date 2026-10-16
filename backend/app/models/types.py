from sqlalchemy import BigInteger, Integer, DateTime
from sqlalchemy.dialects import mysql, sqlite

# Reusable MySQL-compatible types that also work seamlessly on SQLite
BigIntId = BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql").with_variant(Integer, "sqlite")
IntUnsigned = Integer().with_variant(mysql.INTEGER(unsigned=True), "mysql").with_variant(Integer, "sqlite")
DateTime6 = DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")
