FROM python:3.7 as builder

WORKDIR /app
COPY Pipfile* /app/
RUN pip install --upgrade pip && pip install pipenv && pipenv lock --requirements > requirements.txt

FROM python:3.7
COPY dialog-mentions-tracker-bot /app
COPY --from=builder /app/requirements.txt /app/
RUN pip install -r /app/requirements.txt && mkdir /app/backup && echo "{}" > /app/backup/reminder.json && echo "{}" > /app/backup/tracked_users.json

EXPOSE 8080

CMD ["python3", "/app/main.py"]