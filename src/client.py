import grpc
import argparse
import asyncio

import video_transfer_pb2
import video_transfer_pb2_grpc

class Client():

    def __init__(self, ip, file_name, video_name):
        self.ip = ip
        self.file_name = file_name
        self.video_name = video_name
        self.chunk_size = 1024 * 1024 #1MB

    async def chunk_out_video(self):
        with open(self.file_name, 'rb') as fp:
            while chunk := fp.read(self.chunk_size):
                yield video_transfer_pb2.UploadRequest(video_data=chunk, video_name=self.video_name)

    async def Upload(self):
        async with grpc.aio.insecure_channel(self.ip) as channel:
            stub = video_transfer_pb2_grpc.VideoTransferServiceStub(channel)
            response = await stub.Upload(self.chunk_out_video())
            print(response.ack, response.status_msg)

    async def Download(self):
        async with grpc.aio.insecure_channel(self.ip) as channel:
            stub = video_transfer_pb2_grpc.VideoTransferServiceStub(channel)
            video_stream = stub.Download(video_transfer_pb2.DownloadRequest(video_name=self.file_name))
            with open(f"encoded_{self.video_name}", "wb") as fp:
                async for response in video_stream:
                    fp.write(response.video_data)

if __name__ == "__main__":
    arg_parse = argparse.ArgumentParser() 
    arg_parse.add_argument("--ip", type=str, default="0.0.0.0:50051")
    arg_parse.add_argument("--file", type=str)
    arg_parse.add_argument("--video_name", type=str)
    arg_parse.add_argument("--action", type=str, choices=["upload", "download"], default="upload")
    arg = arg_parse.parse_args()
    client = Client(ip=arg.ip, file_name=arg.file, video_name=arg.video_name)

    if arg.action == "upload":
        asyncio.run(client.Upload())
    if arg.action == "download":
        asyncio.run(client.Download())

    
