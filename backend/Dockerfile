FROM python:3.12-slim AS builder 

WORKDIR /app

COPY backend/requirements.txt .
#best to use virtual env for small image size as pip wheel is bigger
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install -r requirements.txt


FROM python:3.12-slim AS runner

WORKDIR /app
#-M flag makes a systerm user with no home or bin
RUN mkdir -p /app/logs && groupadd usr_grp && useradd -M -g usr_grp usr


COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

#only copy needed files to run to reduce image size
#COPY app.py claude_api.py chatgpt_api.py /app/
COPY backend/ /app/
COPY frontend/ /app/
# this is only for testing now with k8s to have frontend files in backend

RUN  chown -R usr:usr_grp .

USER usr

EXPOSE 8000



CMD [ "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000" ]