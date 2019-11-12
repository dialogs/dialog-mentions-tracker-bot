import json
import threading

from bot import Bot
import os
import yaml


def config_validate(cfg):
    for param in ["bot", "commands"]:
        if param not in cfg:
            raise Exception("Config have not {} configuration".format(param))
    for param in ["endpoint", "token"]:
        if param not in cfg["bot"]:
            raise Exception("Config have not {} configuration in 'bot'".format(param))
    for param in ["start", "stop", 'get_mentions', 'get_groups', 'set_reminder', 'help']:
        if param not in cfg["commands"]:
            raise Exception("Config have not {} configuration in 'commands'".format(param))
    if "timezone" not in cfg:
        cfg["timezone"] = "+0300"


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
    with open(os.path.dirname(__file__) + '/config.yml') as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    config_validate(config)
    bot = Bot(config)

    try:
        bot.start()
    except:
        backup()
        raise Exception("Bot is dead")
