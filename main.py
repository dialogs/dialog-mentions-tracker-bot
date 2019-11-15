import json
import threading
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


def backup_users(users):
    res = {}
    for id_, data in users.items():
        res[id_] = list(data.groups)
    return res


def backup():
    with open(os.path.dirname(__file__) + '/backup/reminder.json', 'w') as f:
        json.dump(bot.reminder, f)
    with open(os.path.dirname(__file__) + '/backup/tracked_users.json', 'w') as f:
        tracked_users = backup_users(bot.tracked_users)
        json.dump(tracked_users, f)
    print('backup complete')


if __name__ == '__main__':
    i18n.load_path.append(os.path.dirname(__file__) + '/translations')
    with open(os.path.dirname(__file__) + '/config.yml') as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    config_validate(config)
    bot = Bot(config)

    try:
        bot.start()
    except:
        backup()
        raise Exception("Bot is dead")
