import yaml
import logging
import logging.config
from importlib.resources import files, as_file

class Logger():

    managed_logs = ['', 'notion_issues']

    def __init__(self, name):
        self.name = name
        self.load_config()
        self.log = logging.getLogger(name)

    def load_config(self):
        logging_config = files('notion_issues.conf').joinpath('logging.yaml')
        with as_file(logging_config) as conf:
            with conf.open() as c:
                logging.config.dictConfig(yaml.load(c, Loader=yaml.Loader))

    def __getattr__(self, attr):
        if hasattr(self.log, attr):
            return getattr(self.log, attr)
        raise AttributeError(f'{self.log.__class__.__name__}.{attr} doesnt exist')

    def verbose(self):
        for log in self.managed_logs:
            logging.getLogger(log).setLevel(logging.DEBUG)
