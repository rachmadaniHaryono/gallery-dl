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

    def get_resized_img_url(self):
        """Get resized url."""
        if self.url.value.startswith(('javascript:', '../')):
            return self.url.value
        noscheme_url = self.url.value.split('://', 1)[1]
        return 'https://i.scaley.io/300-border-bg-white/{}'.format(
            noscheme_url)

    def is_video(self):
        """Return True if it url is video url."""
        if self.url.value.endswith('.mp4'):
            return True
        return False


class PostMetadata(BaseModel):
    """Post."""

    post = ForeignKeyField(Post)
    metadata = JSONField(null=True)
