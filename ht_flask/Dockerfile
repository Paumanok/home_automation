FROM python:3.11.0

ENV GROUP_ID=1000 \
	USER_ID=1000

ENV PYTHONUNBUFFERED=0
WORKDIR = /flask_app/

ENV TZ America/New_York

RUN pip install --upgrade pip
RUN pip install pymongo flask tabulate gunicorn jinja2 plotly pandas kaleido


EXPOSE 5000



CMD ["python", "-u","/flask_app/main.py"]
