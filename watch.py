import zmqsub
import sys
import time
import pprint

if __name__ == '__main__' :
	sub = zmqsub.JSONZMQSub(sys.argv[1])
	while True :
		pprint.pprint(sub.last_msg())
		time.sleep(1.0)
