# USAGE
# python pi_object_detection.py --prototxt MobileNetSSD_deploy.prototxt.txt --model MobileNetSSD_deploy.caffemodel

# import the necessary packages
from imutils.video import VideoStream
from imutils.video import FPS
from multiprocessing import Process
from multiprocessing import Queue

import numpy as np
import argparse
import imutils
import time
import cv2


from flask import Flask, render_template, Response

app = Flask(__name__)

def classify_frame(net, inputQueue, outputQueue):
	# keep looping
	while True:
		# check to see if there is a frame in our input queue
		if not inputQueue.empty():
			# grab the frame from the input queue, resize it, and
			# construct a blob from it
			frame = inputQueue.get()
			frame = cv2.resize(frame, (300, 300))
			blob = cv2.dnn.blobFromImage(frame, 0.007843,
				(300, 300), 127.5)

			# set the blob as input to our deep learning object
			# detector and obtain the detections
			net.setInput(blob)
			detections = net.forward()

			# write the detections to the output queue
			outputQueue.put(detections)


# loop over the frames from the video stream
def gen():
	# construct the argument parse and parse the arguments
	ap = argparse.ArgumentParser()
	ap.add_argument("-p", "--prototxt", required=True,
		help="path to Caffe 'deploy' prototxt file")
	ap.add_argument("-m", "--model", required=True,
		help="path to Caffe pre-trained model")
	ap.add_argument("-c", "--confidence", type=float, default=0.2,
		help="minimum probability to filter weak detections")
	args = vars(ap.parse_args())
	
	# initialize the list of class labels MobileNet SSD was trained to
	# detect, then generate a set of bounding box colors for each class
	CLASSES = ["background", "aeroplane", "bicycle", "bird", "boat",
		"bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
		"dog", "horse", "motorbike", "person", "pottedplant", "sheep",
		"sofa", "train", "tvmonitor"]
	COLORS = np.random.uniform(0, 255, size=(len(CLASSES), 3))
	
	# load our serialized model from disk
	print("[INFO] loading model...")
	net = cv2.dnn.readNetFromCaffe(args["prototxt"], args["model"])
	
	# initialize the input queue (frames), output queue (detections),
	# and the list of actual detections returned by the child process
	inputQueue = Queue(maxsize=1)
	outputQueue = Queue(maxsize=1)
	detections = None
	
	# construct a child process *indepedent* from our main process of
	# execution
	print("[INFO] starting process...")
	p = Process(target=classify_frame, args=(net, inputQueue,
		outputQueue,))
	p.daemon = True
	p.start()
	
	# initialize the video stream, allow the cammera sensor to warmup,
	# and initialize the FPS counter
	print("[INFO] starting video stream...")
	# vs = VideoStream(src=0).start()
	#fps = FPS().start()

	vs = VideoStream(usePiCamera=True).start()
	time.sleep(2.0)
	while True:
		# grab the frame from the threaded video stream, resize it, and
		# grab its imensions
		frame = vs.read()
		frame = imutils.resize(frame, width=400)
		(fH, fW) = frame.shape[:2]
	
		# if the input queue *is* empty, give the current frame to
		# classify
		if inputQueue.empty():
			inputQueue.put(frame)
	
		# if the output queue *is not* empty, grab the detections
		if not outputQueue.empty():
			detections = outputQueue.get()
	
		# check to see if our detectios are not None (and if so, we'll
		# draw the detections on the frame)
		if detections is not None:
			# loop over the detections
			for i in np.arange(0, detections.shape[2]):
				# extract the confidence (i.e., probability) associated
				# with the prediction
				confidence = detections[0, 0, i, 2]
	
				# filter out weak detections by ensuring the `confidence`
				# is greater than the minimum confidence
				if confidence < args["confidence"]:
					continue
	
				# otherwise, extract the index of the class label from
				# the `detections`, then compute the (x, y)-coordinates
				# of the bounding box for the object
				idx = int(detections[0, 0, i, 1])
				dims = np.array([fW, fH, fW, fH])
				box = detections[0, 0, i, 3:7] * dims
				(startX, startY, endX, endY) = box.astype("int")

				# draw the prediction on the frame
				label = "{}: {:.2f}%".format(CLASSES[idx],
					confidence * 100)
				# uncomment the next line to print to terminal the class found
				#print(CLASSES[idx])
				cv2.rectangle(frame, (startX, startY), (endX, endY),
					COLORS[idx], 2)
				y = startY - 15 if startY - 15 > 15 else startY + 15
				cv2.putText(frame, label, (startX, y),
					cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLORS[idx], 2)
		# create jpeg frame for our index.html
		ret, jpeg = cv2.imencode('.jpg', frame)
		htmlframe = jpeg.tobytes()
		yield (b'--frame\r\n'
			b'Content-Type: image/jpeg\r\n\r\n' + htmlframe + b'\r\n\r\n')
	vs.stop()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(gen(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
	app.run(host='192.168.0.55', debug=True)
