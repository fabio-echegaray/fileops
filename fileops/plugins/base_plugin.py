class BaseFileOpsPlugin:
    description: str

    def __init__(self):
        super().__init__()

    def process(self, *args, **kwargs):
        raise NotImplementedError
