FROM python:alpine AS builder 

WORKDIR /app

COPY requirements.txt .

RUN pip wheel --no-cache --wheel-dir wheels -r requirements.txt


FROM python:alpine AS runner

WORKDIR /app

RUN addgroup usr_grp && adduser -S -g usr_grp usr

COPY --from=builder /app/wheels /wheels
RUN pip install /wheels/* && rm -rf /wheels


COPY . .

RUN  chown -R usr:usr_grp .

USER usr

EXPOSE 8000


CMD [ "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000" ]