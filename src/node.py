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
        
        # FFMPEG to segment a video into multiple clips. Change segment_time for different lengths
        segment_dir = f"{self.node.directory}/{first_chunk.video_name}_segments/" 
        os.makedirs(segment_dir, exist_ok=True)
        output_pattern = os.path.join(segment_dir, 'segment%04d.mp4')
        ffmpeg.input(filepath).output(
            output_pattern, 
            f="segment",
            segment_time=5,
            reset_timestamps=1,
            c="copy"
        ).run()

        # Distribute the list of files to all nodes on the network.
        # Track via a hashmap for now (Non Persistent)
        segment_files = sorted([file for file in os.listdir(segment_dir)])

        # Round Robin Assigment : Each segment gets a node
        segment_assignment = dict()
        for node in self.node.network:
            segment_assignment[node] = set()
        network_index = 0
        for segment in segment_files:
            node = self.node.network[network_index]
            segment_assignment[node].add(segment)
            network_index = (network_index + 1) % len(self.node.network)
        self.node.video_map[first_chunk.video_name] = segment_assignment

        

        # Helper function to convert segments into streams
        async def segment_to_stream(segment_name, video_name):
            with open(f"{segment_dir}{segment_name}", 'rb') as fp:
                while chunk := fp.read(1024*1024):
                    yield video_encode_pb2.EncodeSegmentRequest(video_data=chunk, video_name=video_name, segment_name=segment_name)

        # Helper to encode assigned segments on each node. Run via asyncio's gather
        async def encode_on_node(node):
            async with grpc.aio.insecure_channel(node) as channel:
                stub = video_encode_pb2_grpc.SegmentEncodeServiceStub(channel)
                node_tasks = []
                for segment in segment_assignment[node]:
                    # Timeout in this instance refers to how much time per process. Had it at 5 seconds, but might be too little. Bumped to 90 seconds for now.
                    node_tasks.append(stub.EncodeVideoSegment(segment_to_stream(segment_name=segment, video_name=first_chunk.video_name), timeout=90))
                return await asyncio.gather(*node_tasks)


        # Create stub on each network node to call encode service with each segment file as argument, done in parallel io calls.
        encoding_task = []
        for node in self.node.network:
            encoding_task.append(encode_on_node(node))
        await asyncio.gather(*encoding_task)
        return video_transfer_pb2.UploadResponse(ack=True, status_msg="File Upload Completed")


    # Gather all encoded segments and stitch it back together
    def Download(self, request, context):
        pass




class SegmentEncodeImplService(video_encode_pb2_grpc.SegmentEncodeServiceServicer):
    def __init__(self, node):
        self.node = node

    async def EncodeVideoSegment(self, request_iterator, context):
        first_chunk = await anext(request_iterator)
        encode_dir = f"{self.node.directory}/encode/{first_chunk.video_name}/" 
        os.makedirs(encode_dir, exist_ok=True)
        segment_file_path = f"{encode_dir}/{first_chunk.segment_name}"
        with open(segment_file_path, "wb") as fp:
            fp.write(first_chunk.video_data)
            async for chunk in request_iterator:
                fp.write(chunk.video_data)

        encode_file_path = f"{encode_dir}encoded_{first_chunk.segment_name}"
        ffmpeg.input(segment_file_path).output(encode_file_path, vcodec='libx264', crf=28, preset='fast').overwrite_output().run()

        return video_encode_pb2.EncodeSegmentResponse(success=True, status_message="Done", segment_name=first_chunk.segment_name) 

    def RetrieveVideoSegment(self, request, context):
        pass 

    

class Node():
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.directory = f"/tmp/{self.port}" 
        os.makedirs(self.directory, exist_ok=True)

        # Currently for workers, should not include master node -> troll but my master can't handle load atm.
        # TODO: move this to a configurable file
        self.network = ["0.0.0.0:50052",
                        "0.0.0.0:50053"]

        # TODO: flush map to disk for persistence.
        self.video_map = dict()


    async def serve(self):
        server = grpc.aio.server() 
        video_transfer_pb2_grpc.add_VideoTransferServiceServicer_to_server(VideoTransferImplService(self), server)
        video_encode_pb2_grpc.add_SegmentEncodeServiceServicer_to_server(SegmentEncodeImplService(self), server)
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
