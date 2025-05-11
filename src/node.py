import grpc
import asyncio
import argparse
import logging
import os
import ffmpeg


from builtins import anext
# all the proto buffer imports
import video_encode_pb2
import video_encode_pb2_grpc
import video_transfer_pb2
import video_transfer_pb2_grpc



class VideoTransferImplService(video_transfer_pb2_grpc.VideoTransferServiceServicer):
    def __init__(self, node):
        self.node = node

    # Maintain a record of uploaded file 
    # Spreads it out across the network
    async def Upload(self, request_iterator, context):
        
        # Get metadata of what the file is on the first chunk
        first_chunk = await anext(request_iterator)
        logging.info(f"Received RPC call for video: {first_chunk.video_name}")
        filepath = f"{self.node.directory}/{first_chunk.video_name}"
        logging.info(f"Upload rpc called on {filepath}")

        with open(filepath, "wb") as fp:
            fp.write(first_chunk.video_data)
            # write the remaining chunks out to disk
            async for chunk in request_iterator:
                fp.write(chunk.video_data)
        
        # FFMPEG to segment a video into multiple clips
        segment_dir = f"{filepath}/{first_chunk.video_name}_segments/" 
        os.makedirs(segment_dir, exist_ok=True)

        output_pattern = os.path.join(segment_dir, 'output_%04d.mp4')
        ffmpeg.input(filepath).output(
            output_pattern, 
            f="segment",
            segment_time=5,
            reset_timestamps=1,
            c="copy"
        ).run()

        return video_transfer_pb2.UploadResponse(ack=True, status_msg="File Upload Completed")

    # Gather all encoded segments and stitch it back together
    def Download(self, request, context):
        pass

class VideoEncodeImplService(video_encode_pb2_grpc.VideoEncodeServiceServicer):
    def EncodeVideoSegment(self, request_iterator, context):
        pass

    def RetrieveVideoSegment(self, request, context):
        pass 

    

class Node():
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.directory = f"/tmp/{self.port}" 
        self.network = ["0.0.0.0:50051",
                        "0.0.0.0:50052",]

        os.makedirs(self.directory, exist_ok=True)

    async def serve(self):
        server = grpc.aio.server() 
        video_transfer_pb2_grpc.add_VideoTransferServiceServicer_to_server(VideoTransferImplService(self), server)
        video_encode_pb2_grpc.add_VideoEncodeServiceServicer_to_server(VideoEncodeImplService(), server)
        server.add_insecure_port(f"{self.ip}:{self.port}")
        logging.info(f"Starting server on {self.ip}:{self.port}")
        await server.start()
        await server.wait_for_termination()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=str, default="50051")
    parser.add_argument("--ip", type=str, default="0.0.0.0")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(Node(ip=args.ip, port=args.port).serve())
