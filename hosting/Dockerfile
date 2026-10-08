FROM python:3.12-slim
WORKDIR /app
COPY coordinator.py /app/
USER 65534:65534
ENV PORT=8000
EXPOSE 8000
CMD ["python", "coordinator.py"]
