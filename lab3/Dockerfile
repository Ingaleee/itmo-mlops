FROM python@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TOKENIZERS_PARALLELISM=false
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock && pip check
COPY model/fetch_tokenizer.py model/fetch_model.py model/Modelfile ./model/
RUN python model/fetch_tokenizer.py
COPY app ./app
RUN mkdir /app/artifacts && chown 10001:10001 /app/artifacts
USER 10001:10001
EXPOSE 8000
CMD ["python","-m","uvicorn","app.portal:create_app","--factory","--host","0.0.0.0","--port","8000","--no-access-log"]
