import json
import os
import threading
from datetime import datetime

import grpc
from dialog_api import messaging_pb2, sequence_and_updates_pb2, peers_pb2, groups_pb2
from dialog_bot_sdk import interactive_media
from dialog_bot_sdk.bot import DialogBot

from Groups import Group
from Users import User


HOURS = {}
MINUTES = {}
MAGIC_CONST = 1000

for i in range(25):
    HOURS[str(i)] = str(i)
for i in range(60):
    MINUTES[str(i)] = str(i)


class Bot:
    def __init__(self, config):
        bot = config["bot"]
        self.commands = config["commands"]
        self.timezone = config["timezone"]
        self.bot = DialogBot.get_secure_bot(
            bot["endpoint"],
            grpc.ssl_channel_credentials(),
            bot["token"]
        )
        self.tracked_users = {}
        self.default_tracked_groups = {}
        self.reminder = {}
        self.cron_time = 60

    def cron(self):
        ticker = threading.Event()
        while not ticker.wait(self.cron_time):
            t = datetime.now(datetime.strptime("+0300", "%z").tzinfo)
            self.cron_time = 60 - int(t.strftime("%S"))
            time = t.strftime("%H:%M")
            if time in self.reminder:
                for uid in self.reminder[time]:
                    peer = peers_pb2.Peer(type=peers_pb2.PEERTYPE_PRIVATE, id=uid)
                    self.send_mentions_for_user(peer)

    def on_msg(self, *params):
        message = params[0].message
        sender_id = params[0].sender_uid
        text = message.textMessage.text
        service = params[0].message.serviceMessage
        peer = params[0].peer
        if service:
            self.processing_service_message(service, sender_id, peer)
        if not text:
            return
        if peer.type == 2:
            self.check_mention_in_message(message.textMessage, peer.id, params[0].mid)
        elif text == self.commands["start"]:
            if peer.id not in self.tracked_users:
                self.add_tracked_user(peer)
                self.bot.messaging.send_message(peer, "Tracking start.")
            else:
                self.bot.messaging.send_message(peer, "I'm already track yours mentions.")
        elif text == self.commands["stop"]:
            if peer.id in self.tracked_users:
                self.drop_remind(peer.id)
                self.tracked_users.pop(peer.id)
                self.bot.messaging.send_message(peer, "Tracking stop.")
            else:
                self.bot.messaging.send_message(peer, "I didn't track yours mentions.")
        elif text == self.commands["get_mentions"]:
            if peer.id in self.tracked_users:
                self.send_mentions_for_user(peer)
                self.tracked_users[peer.id].mentions = {}
            else:
                self.bot.messaging.send_message(peer, 'I didn\'t track yours mentions. Send "{}" to start '
                                                      'tracking.'.format(self.commands["start"]))
        elif text == self.commands["get_groups"]:
            if peer.id in self.tracked_users:
                self.get_tracked_groups_for_user(peer)
            else:
                self.bot.messaging.send_message(peer, 'I didn\'t track yours mentions. Send "{0}" to start '
                                                      'tracking.'.format(self.commands["start"]))
        elif text == self.commands["set_reminder"]:
            if peer.id in self.tracked_users:
                self.bot.messaging.send_message(peer, "Set reminder time:", self.interactive_reminder())
            else:
                self.bot.messaging.send_message(peer, 'I didn\'t track yours mentions. Send "{0}" to start '
                                                      'tracking.'.format(self.commands["start"]))
        elif text == self.commands["help"]:
            self.get_commands(peer)
        else:
            self.bot.messaging.send_message(peer, 'Unknown command. Send "{}" to get a list of commands.'
                                            .format(self.commands['help']))

    def on_event(self, *params):
        uid = params[0].uid
        peer = peers_pb2.Peer(type=peers_pb2.PEERTYPE_PRIVATE, id=uid)
        which_button = params[0].value
        msg = self.bot.messaging.get_messages_by_id([params[0].mid])[0]
        if which_button == "Start":
            self.on_click_start(int(params[0].id), peer, msg)
        elif which_button == "Stop":
            self.on_click_stop(int(params[0].id), peer, msg)
        elif params[0].id == "hours":
            self.on_select(peer, params[0].mid, msg, which_button, "")
        elif params[0].id == "minutes":
            self.on_select(peer, params[0].mid, msg, "", which_button)

    def get_commands(self, peer):
        text = '"{0}": subscribe on tracking your mentions,\n' \
               '"{1}": unsubscribe your tracking,\n' \
               '"{2}": get your mentions since "{0}" or last reminder or last used this option,\n' \
               '"{3}": set reminder which will remind about your mentions every day in due time,\n' \
               '"{4}": get groups to which I am subscribed for you can subscribe/unsubscribe on them'\
            .format(self.commands["start"], self.commands["stop"], self.commands["get_mentions"],
                    self.commands["set_reminder"], self.commands["get_groups"])
        return self.bot.messaging.send_message(peer, text)

    def start(self):
        self.preprocessing_from_backup()
        self.get_default_groups()
        self.bot.messaging.on_message_async(self.on_msg, self.on_event)
        self.cron()

    def get_default_groups(self):
        groups = self.get_groups()
        for group in groups:
            g = self.get_group(group)
            if g is not None:
                self.default_tracked_groups[group.id] = g

    def get_group(self, group):
        peer = peers_pb2.OutPeer(id=group.id, type=peers_pb2.PEERTYPE_GROUP, access_hash=group.access_hash)
        users = self.get_user_ids_in_group(peer)
        if self.bot.user_info.user.id not in users:
            return
        invite_url = self.bot.internal.groups.GetGroupInviteUrl(
            groups_pb2.RequestGetGroupInviteUrl(group_peer=peers_pb2.GroupOutPeer(group_id=group.id,
                                                                                  access_hash=group.access_hash))
        ).url
        return Group(peer, users, group.data.title, group.data.shortname.value, invite_url)

    def get_groups(self):
        contacts = self.bot.internal.messaging.LoadDialogs(messaging_pb2.RequestLoadDialogs()).group_peers
        return self.bot.internal.updates.GetReferencedEntitites(
            sequence_and_updates_pb2.RequestGetReferencedEntitites(
                groups=contacts
            )
        ).groups

    def check_mention_in_message(self, msg, gid, mid):
        if msg.mentions:
            for id_ in msg.mentions:
                if id_ in self.tracked_users:
                    self.add_mention(id_, gid, mid)
                elif id_ == 0:
                    for user_id in self.default_tracked_groups[gid].user_ids:
                        if user_id in msg.mentions:
                            continue
                        self.add_mention(user_id, gid, mid)

    def add_mention(self, uid, gid, mid):
        if gid not in self.tracked_users[uid].groups:
            return
        if gid in self.tracked_users[uid].mentions:
            self.tracked_users[uid].mentions[gid].append(mid)
        else:
            self.tracked_users[uid].mentions[gid] = [mid]

    def add_tracked_user(self, peer):
        self.tracked_users[peer.id] = User(self.bot.manager.get_outpeer(peer), self.get_default_groups_for_user(peer))

    def get_default_groups_for_user(self, peer):
        result = set()
        for id_, group in self.default_tracked_groups.items():
            if peer.id in group.user_ids:
                result.add(id_)
        return result

    def get_tracked_groups_for_user(self, peer):
        while self.tracked_users[peer.id].buttons_mids:
            message = self.bot.messaging.get_messages_by_id([self.tracked_users[peer.id].buttons_mids.pop()])[0]
            self.bot.messaging.update_message(message, message.message.textMessage.text)
        for id_, group in self.default_tracked_groups.items():
            if peer.id not in group.user_ids:
                continue
            if id_ in self.tracked_users[peer.id].groups:
                interactive = self.interactive_stop(id_)
            else:
                interactive = self.interactive_start(id_)
            self.tracked_users[peer.id].buttons_mids.append(
                self.bot.messaging.send_message(peer, self.get_shortname_or_url_group(group), interactive).message_id)

    @staticmethod
    def interactive_stop(gid):
        return [interactive_media.InteractiveMediaGroup(
            [
                interactive_media.InteractiveMedia(
                    gid,
                    interactive_media.InteractiveMediaButton("Stop", "Stop tracking")
                ),
            ]
        )]

    @staticmethod
    def interactive_start(gid):
        return [interactive_media.InteractiveMediaGroup(
            [
                interactive_media.InteractiveMedia(
                    gid,
                    interactive_media.InteractiveMediaButton("Start", "Start tracking")
                ),
            ]
        )]

    @staticmethod
    def interactive_reminder():
        return [interactive_media.InteractiveMediaGroup(
            [
                interactive_media.InteractiveMedia(
                    "hours",
                    interactive_media.InteractiveMediaSelect(HOURS, "Hour", "Hour")
                ),
                interactive_media.InteractiveMedia(
                    "minutes",
                    interactive_media.InteractiveMediaSelect(MINUTES, "Minute", "Minute")
                ),
            ]
        )]

    def get_user_ids_in_group(self, peer):
        members = self.bot.groups.load_members(peer, MAGIC_CONST)
        users = set()
        for member in members.users:
            users.add(member.id)
        return users

    def send_mentions_for_user(self, peer):
        user = self.tracked_users[peer.id]
        if not user.mentions:
            self.bot.messaging.send_message(peer, "You have not mentions.")
        for group_id, mids in user.mentions.items():
            group = self.default_tracked_groups[group_id]
            self.bot.messaging.forward(peer, mids, self.get_shortname_or_url_group(group))

    @staticmethod
    def get_shortname_or_url_group(group):
        if group.shortname:
            text = "@{}".format(group.shortname)
        else:
            text = "[{0}]({1})".format(group.title, group.invite_url)
        return text

    def on_click_start(self, event_id, peer, msg):
        uid = peer.id
        text = msg.message.textMessage.text
        if uid not in self.tracked_users:
            self.bot.messaging.send_message(peer, "Oops. You unsubscribed on track mentions. Send '{}' for subscribe."
                                            .format(self.commands["start"]))
            self.bot.messaging.update_message(msg, text)
            return
        group = self.default_tracked_groups[event_id]
        if event_id not in self.tracked_users[uid].groups:
            self.tracked_users[uid].groups.add(event_id)
            self.bot.messaging.send_message(peer, "Start tracking group {} for you.".format(
                self.get_shortname_or_url_group(group)
            ))
        else:
            self.bot.messaging.send_message(peer, "Group already track.")
        self.bot.messaging.update_message(msg, text)

    def on_click_stop(self, event_id, peer, msg):
        uid = peer.id
        text = msg.message.textMessage.text
        if uid not in self.tracked_users:
            self.bot.messaging.send_message(peer, "Oops. You unsubscribed on track mentions. Send '{}' for subscribe."
                                            .format(self.commands["start"]))
            self.bot.messaging.update_message(msg, text)
            return
        group = self.default_tracked_groups[event_id]
        if event_id in self.tracked_users[uid].groups:
            self.tracked_users[uid].groups.remove(event_id)
            self.bot.messaging.send_message(peer, "Stop tracking group {} for you.".format(
                self.get_shortname_or_url_group(group)
            ))
        else:
            self.bot.messaging.send_message(peer, "I didn't track yours mentions in {}.".format(
                self.get_shortname_or_url_group(group)
            ))
        self.bot.messaging.update_message(msg, text)

    def on_select(self, peer, mid, msg, hour, minute):
        uid = peer.id
        text = msg.message.textMessage.text
        if uid not in self.tracked_users:
            self.bot.messaging.send_message(peer, "Oops. You unsubscribed on track mentions. Send '{}' for subscribe."
                                            .format(self.commands["start"]))
            self.bot.messaging.update_message(msg, text)
            return
        for remind in self.tracked_users[uid].reminder:
            if mid == remind[0]:
                if remind[1] and minute or hour and remind[2]:
                    if remind[2]:
                        minute = remind[2]
                    else:
                        minute = "0" * (2 - len(minute)) + minute

                    if remind[1]:
                        hour = remind[1]
                    else:
                        hour = "0" * (2 - len(hour)) + hour

                    time = "{0}:{1}".format(hour, minute)

                    if time in self.reminder:
                        self.reminder[time].append(uid)
                    else:
                        self.reminder[time] = [uid]
                    for reminder in self.tracked_users[uid].reminder:
                        mid = reminder[0]
                        message = self.bot.messaging.get_messages_by_id([mid])[0]
                        self.bot.messaging.update_message(message, message.message.textMessage.text)
                    self.tracked_users[uid].reminder = []
                    self.drop_remind(uid)
                    self.tracked_users[uid].remind_time = time
                    self.bot.messaging.update_message(msg, text)
                    self.bot.messaging.send_message(peer, "I will remind you of yours mentions at {} every day."
                                                    .format(time))
                elif hour:
                    remind[1] = "0" * (2 - len(hour)) + hour
                else:
                    remind[2] = "0" * (2 - len(minute)) + minute
                return
        self.tracked_users[uid].reminder.append((mid, hour, minute))

    def processing_service_message(self, service_msg, sender_id, peer):
        if "User kicked the group" == service_msg.text:
            kick = service_msg.ext.userKicked.kicked_uid
            if kick == self.bot.user_info.user.id:
                self.default_tracked_groups.pop(peer.id)
            else:
                if kick in self.default_tracked_groups[peer.id].user_ids:
                    self.default_tracked_groups[peer.id].user_ids.remove(kick)
                if kick in self.tracked_users and peer.id in self.tracked_users[kick].groups:
                    self.tracked_users[kick].groups.remove(peer.id)
        elif 'User joined the group' == service_msg.text:
            if peer.id in self.default_tracked_groups:
                self.default_tracked_groups[peer.id].user_ids.add(sender_id)
                if sender_id in self.tracked_users:
                    self.tracked_users[sender_id].groups.add(peer.id)
            else:
                groups = self.get_groups()
                for group in groups:
                    if group.id == peer.id:
                        self.default_tracked_groups[peer.id] = self.get_group(group)
        elif "User left the group" == service_msg.text:
            if sender_id in self.tracked_users:
                if peer.id in self.tracked_users[sender_id].groups:
                    self.tracked_users[sender_id].groups.remove(sender_id)
                if sender_id in self.default_tracked_groups[peer.id].users:
                    self.default_tracked_groups[peer.id].users.remove(sender_id)

    def preprocessing_from_backup(self):
        if os.path.exists(os.path.dirname(__file__) + '/backup/reminder.json'):
            with open(os.path.dirname(__file__) + '/backup/reminder.json') as reminder:
                self.reminder = json.load(reminder)
        if os.path.exists(os.path.dirname(__file__) + '/backup/tracked_users.json'):
            with open(os.path.dirname(__file__) + '/backup/tracked_users.json') as tracked_users:
                tracked = json.load(tracked_users)
                for id_, groups in tracked.items():
                    peer = peers_pb2.Peer(type=peers_pb2.PEERTYPE_PRIVATE, id=int(id_))
                    self.tracked_users[int(id_)] = User(self.bot.manager.get_outpeer(peer), set(groups))
        if self.tracked_users and self.reminder:
            for time, ids in self.reminder.items():
                for id_ in ids:
                    self.tracked_users[id_].remind_time = time

    def drop_remind(self, uid):
        if self.tracked_users[uid].remind_time is not None:
            last_time = self.tracked_users[uid].remind_time
            if uid in self.reminder[last_time]:
                self.reminder[last_time].remove(uid)
                if not self.reminder[last_time]:
                    self.reminder.pop(last_time)
