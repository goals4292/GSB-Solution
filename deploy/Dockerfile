FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    HOME=/tmp/gsb-home JUPYTER_RUNTIME_DIR=/tmp/gsb-runtime
WORKDIR /opt/gsb
COPY requirements-tested.txt ./requirements-tested.txt
RUN pip install --no-cache-dir -r requirements-tested.txt
COPY deploy/jupyter_shared_config.py ./jupyter_shared_config.py
WORKDIR /workspace
USER 1000:1000
EXPOSE 8888
CMD ["python", "-m", "jupyterlab", "--config=/opt/gsb/jupyter_shared_config.py"]
