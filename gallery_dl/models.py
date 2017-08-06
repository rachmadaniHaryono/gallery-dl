from peewee import *

db = SqliteDatabase(None)

class Gallery(Model):
    src_url = CharField()
    index = IntegerField()
    url = CharField()
    # from info dict
    artist = CharField(null=True)
    count = CharField(null=True)
    extension = CharField(null=True)
    image_id = CharField(null=True)
    lang = CharField(null=True)
    language = CharField(null=True)
    name = CharField(null=True)
    num = IntegerField(null=True)
    section = CharField(null=True)
    tags = CharField(null=True)
    title = CharField(null=True)

    def to_dataset(self):
        return [
            self.index, self.url,
            {
                'artist': self.artist,
                'count': self.count,
                'extension': self.extension,
                'image-id': self.image_id,
                'lang': self.lang,
                'language': self.language,
                'name': self.name,
                'num': self.num,
                'section': self.section,
                'tags': self.tags,
                'title': self.title,
            }
        ]

    @staticmethod
    def save_from_dataset(dataset, src_url):
        dataset_info = dataset[2]
        image_id = dataset_info.pop('image-id', None)
        obj = Gallery(
            src_url=src_url, index=dataset[0], url=dataset[1], imagee_id=image_id, **dataset_info)
        obj.save()
        return obj


    class Meta:
        database = db # This model uses the "people.db" database.
