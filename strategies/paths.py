import os


class Paths:
    base = os.path.dirname(__file__)
    ui_files = os.path.join(base, "ui")
    images = os.path.join(base, "images")
    icons = os.path.join(images, "icons")
    datas = os.path.join(base, "data")
    logs = os.path.join(base, "logs")

    # File loaders.
    @classmethod
    def ui_file(cls, filename):
        return os.path.join(cls.ui_files, filename)

    @classmethod
    def icon(cls, filename):
        return os.path.join(cls.icons, filename)

    @classmethod
    def image(cls, filename):
        return os.path.join(cls.images, filename)

    @classmethod
    def data(cls, filename):
        return os.path.join(cls.datas, filename)

    @classmethod
    def log(cls, filename):
        return os.path.join(cls.logs, filename)

if __name__=='__main__':
    print(Paths.ui_file)
    print(Paths.log('mylog.log'))
