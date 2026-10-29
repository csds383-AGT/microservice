FROM python:3.14-slim
WORKDIR /festhub

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY concerts/concerts.proto artists/artists.proto categories/categories.proto media/media.proto protos/
RUN python -m grpc_tools.protoc \
    -I protos \
    --python_out=. \
    --grpc_python_out=. \
    protos/*.proto

COPY common common
COPY artists/service.py artists/server.py ./

CMD ["python", "server.py"]
