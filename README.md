
dialog-mentions-tracker-bot
=

Config
-
bot - for start bot
- token
- endpoint

commands - what will be called bot's commands on client 
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