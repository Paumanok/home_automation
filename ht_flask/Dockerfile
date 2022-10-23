FROM python:3.8.2-alpine

ENV GROUP_ID=1000 \
	USER_ID=1000

ENV PYTHONUNBUFFERED=0
WORKDIR = /flask_app/

RUN apk add --no-cache tzdata
ENV TZ America/New_York
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN apk --no-cache --update-cache add gcc gfortran python python-dev py-pip build-base wget freetype-dev libpng-dev openblas-dev

RUN pip install --upgrade pip

RUN pip install pymongo flask tabulate gunicorn jinja2 plotly pandas

RUN addgroup -g $GROUP_ID www
run adduser -D -u $USER_ID -G www www -s /bin/sh

USER www

EXPOSE 5000

CMD ["python", "-u","/flask_app/main.py"]
