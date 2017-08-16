"""Model module."""
from peewee import (
    SqliteDatabase,
    ForeignKeyField,
    Model,
    CharField,
)
from playhouse.kv import JSONField

db = SqliteDatabase(None)


class BaseModel(Model):
    """Base model."""

    class Meta:
        database = db


class Url(BaseModel):
    """Url Model."""

    value = CharField(unique=True)


class Gallery(BaseModel):
    """Gallery."""

    url = ForeignKeyField(Url, unique=True)
    metadata = JSONField(null=True)


class Post(BaseModel):
    """Post."""

    gallery = ForeignKeyField(Gallery)
    url = ForeignKeyField(Url)


class PostMetadata(BaseModel):
    """Post."""

    post = ForeignKeyField(Post)
    metadata = JSONField(null=True)
