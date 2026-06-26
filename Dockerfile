FROM python:3.11-slim
RUN pip install bleak paho-mqtt
COPY bms.py /bms.py
CMD ["python3", "-u", "/bms.py"]