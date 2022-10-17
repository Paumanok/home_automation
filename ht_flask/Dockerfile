FROM python:3.6.8-alpine3.9

ENV GROUP_ID=1000 \
	USER_ID=1000

ENV PYTHONUNBUFFERED=0
WORKDIR = /flask_app/

RUN apk add --no-cache tzdata
ENV TZ America/New_York
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN pip install pymongo flask tabulate gunicorn jinja2

RUN addgroup -g $GROUP_ID www
run adduser -D -u $USER_ID -G www www -s /bin/sh

USER www

EXPOSE 5000

CMD ["python", "-u","/flask_app/main.py"]
