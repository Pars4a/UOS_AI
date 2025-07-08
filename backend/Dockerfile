FROM python:3.12-alpine AS builder 

WORKDIR /app

COPY requirements.txt .

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install -r requirements.txt


FROM python:3.12-alpine AS runner

WORKDIR /app

RUN mkdir /app/logs && addgroup usr_grp && adduser -S -g usr_grp usr


COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"


COPY app.py claude_api.py chatgpt_api.py /app/


RUN  chown -R usr:usr_grp .

USER usr

EXPOSE 8000



CMD [ "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000" ]