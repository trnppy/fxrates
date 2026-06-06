FROM alpine:latest

# Install bash, python, select python modules
ENV PYTHONUNBUFFERED=1
RUN apk add --update --no-cache bash python3 py3-pandas py3-matplotlib py3-flask py3-setuptools && ln -sf python3 /usr/bin/python

EXPOSE 5000/tcp

COPY fxrates.py /fxrates.py
CMD ["python", "/fxrates.py"]

