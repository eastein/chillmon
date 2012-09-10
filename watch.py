import zmqsub
import sys
import time

if __name__ == '__main__' :
	sub = zmqsub.JSONZMQSub(sys.argv[1])
	while True :
		print sub.last_msg()
		time.sleep(1.0)
