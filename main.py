import i18n

from bot import Bot
import os
import yaml


def config_validate(cfg):
    for param in ["bot", "commands"]:
        if param not in cfg:
            raise Exception("Config has no {} configuration".format(param))
    for param in ["endpoint", "token"]:
        if param not in cfg["bot"]:
            raise Exception("Config has no {} configuration in 'bot'".format(param))
    for param in ["start", "stop", 'get_mentions', 'get_groups', 'set_reminder', 'help']:
        if param not in cfg["commands"]:
            raise Exception("Config has no {} configuration in 'commands'".format(param))
    if "timezone" not in cfg:
        raise Exception("Config has no timezone configuration")
    if "lang" not in cfg:
        raise Exception("Config has no lang configuration")
    if "database" not in cfg:
        raise Exception("Config has no database configuration")


if __name__ == '__main__':
    i18n.load_path.append(os.path.dirname(__file__) + '/translations')
    with open(os.path.dirname(__file__) + '/config.yml') as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    config_validate(config)
    bot = Bot(config)

    bot.start()

