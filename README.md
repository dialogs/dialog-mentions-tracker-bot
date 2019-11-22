
dialog-mentions-tracker-bot
=

Config
-
bot - to start bot
- token
- endpoint

commands - command that the bot has
- start
- stop
- get_mentions
- get_groups
- set_reminder
- help

 Usage
-
​
```bash
docker build -t <image_name> .
docker run --name <container_name> -v $(pwd)/config.yml:/app/config.yml:ro <image_name>
```