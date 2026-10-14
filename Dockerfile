# =============================================================================
# Dockerfile — AtletismoPro Web (Streamlit)
# Optimizado para Render, Hugging Face Spaces o cualquier host Docker.
# =============================================================================

FROM python:3.11-slim

# Establecer directorio de trabajo
WORKDIR /app

# Variables de entorno para evitar prompts interactivos
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ENABLE_CORS=false \
    STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false

# Instalar dependencias del sistema (mínimas)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar solo los archivos necesarios (no la app de escritorio)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente relevante
COPY app.py .
COPY database.py .
COPY export_web.py .
COPY live_stream.py .
COPY seeding.py .
COPY web_template.py .
COPY web_publisher.py .
COPY logo.png .
COPY atletismo.db .

# Exponer el puerto de Streamlit
EXPOSE 8501

# Healthcheck para plataformas como Render
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Comando de arranque
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
