# video_encoding_cmpe275
Class Project for Distributed Video Encoding for SJSU CMPE 275



# ISSUES

Todo items are listed in Issues. Please contact Ignol in discord server for issue assignments. 

If there is a * next to the issue, that means it's a desired but not essential feature.


# Run
- install venv and source venv/bin/activate
- cd src -> ./generate_pb.sh  
- python3 node.py / new terminal -> python3 node.py --port 50052 / new terminal -> python3 node.py --port 50053
- cd examples 
- python3 ../src/client.py --file test.mp4 --ip 0.0.0.0:50051 --video_name test.mp4 --action upload
- python3 ../src/client.py --file test.mp4 --ip 0.0.0.0:50051 --video_name test.mp4 --actoin download
