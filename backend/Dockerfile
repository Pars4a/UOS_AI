FROM python:3.12-slim AS builder 

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --prefix=/packages -r requirements.txt

FROM python:3.12-slim AS runner

WORKDIR /app
#-M flag makes a systerm user with no home or bin
RUN mkdir -p /app/logs && groupadd usr_grp && useradd -M -g usr_grp usr

COPY --from=builder /packages /usr/local/
RUN rm -rf /packages

#only copy needed files to run to reduce image size
#COPY backend/app.py backend/claude_api.py backend/chatgpt_api.py /app/
COPY backend/ /app/
COPY frontend/ /app/
# this is only for testing now with k8s to have frontend files in backend

RUN  chown -R usr:usr_grp .

USER usr

EXPOSE 8000



CMD [ "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000" ]