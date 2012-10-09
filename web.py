import tornado.web
import tornado.ioloop
import zmqsub
import threading
import re
import sys
import time
import os
import concurrent.futures as futures
import traceback

JSOK = re.compile('^[a-z0-9\-_\.]+\.js$')

class ProtoFuture(object) :
	def __init__(self, fut, continuation) :
		#print 'ProtoFuture.__init__'
		self.fut = fut
		self.continuation = continuation
		self.cbs = []
		self.fut.add_done_callback(self.completed)

	def add_done_callback(self, cb) :
		#print 'ProtoFuture.add_done_callback'
		self.cbs.append(cb)

	def completed(self, fut) :
		#print 'ProtoFuture.completed'
		for cb in self.cbs :
			cb(self)

	def result(self) :
		#print 'ProtoFuture.result'
		return self.continuation(self.fut.result())


class TraceThread(threading.Thread) :
	def __init__(self, sock, sample_cap=3600) :
		self.sock = sock
		self.ok = True
		self.samples = []
		self.sample_cap = sample_cap
		threading.Thread.__init__(self)

	def stop(self) :
		self.ok = False

	def get_trace(self, a, b, gt) :
		r = []
		for samp in self.samples :
			ts, sample = samp
			if ts > gt :
				r.append((ts, sample[a][b]))
		return r

	def run(self) :
		while self.ok :
			msg = self.sock.last_msg()
			if not msg :
				time.sleep(0.1)
				continue
	
			samples = self.samples[:]
			samples.append((long(time.time() * 1000), msg))
			self.samples = samples[-self.sample_cap:]

			time.sleep(5.0)

class JSHandler(tornado.web.RequestHandler):
	def get(self, fn):
		if not hasattr(self.__class__, 'fcache') :
			self.__class__.fcache = {}

		if fn not in self.__class__.fcache :
			if not JSOK.match(fn) :
				raise tornado.web.HTTPError(404)

			if not os.path.exists(fn) :
				raise tornado.web.HTTPError(404)

			d = open(fn).read()
			self.__class__.fcache[fn] = d

		self.write(self.__class__.fcache[fn])

class InterfaceHandler(tornado.web.RequestHandler) :
	def get(self) :
		self.write(self.application.__interface__)

class BaseHandler(tornado.web.RequestHandler):
	def wj(self, status, j) :
		self.application.__io_instance__.add_callback(lambda: self._wj(status, j))

	def _wj(self, status, j) :
		self.set_status(status)
		self.set_header('Access-Control-Allow-Origin', '*')
		self.set_header('Cache-Control', 'no-cache')
		self.set_header('Content-Type', 'application/json')
		self.write(j)
		self.finish()

class JSONHandler(BaseHandler):
	NO_WRAP = False

	@tornado.web.asynchronous
	def get(self, *a):
		cn = self.__class__.__name__
		cn += ' ' * (14 - len(cn))
		print '[%s] [json/%s] %s GET args %s' % (time.ctime(), cn, self.request.remote_ip, str(a))
		try :
			result = self.process_request(*a)
		except Exception, e :
			result = e
		
		if isinstance(result, (futures.Future, ProtoFuture)) :
			result.add_done_callback(self.handle_response)
		else :
			self.handle_response(result)

	def handle_response(self, result) :
		error = None
		status = 200
		try :
			if isinstance(result, (futures.Future, ProtoFuture)) :
				result = result.result()
			elif isinstance(result, Exception) :
				traceback.print_exc()
				raise result
			
			if self.NO_WRAP :
				resp = result
			else :
				resp = {'status' : 'ok', 'data' : result}
		except ValueError :
			status = 404
			error = 'bad input'
		except KeyError :
			status = 404
			error = 'not found'
		except :
			status = 500
			print 'exception while fetching deferred result'
			traceback.print_exc()
			error = 'exception'

		if error :
			resp = {'status' : 'failure', 'reason' : error}

		self.wj(status, resp)

class TraceListHandler(JSONHandler):
	def process_request(self):
		ts, i = self.application.__traces__.samples[0]
		return dict([(k,i[k].keys()) for k in i])

class TraceHandler(JSONHandler):
	def process_request(self, tracetype, tracename, *a):
		try :
			gt = long(a[0])
		except :
			gt = 0
		
		return self.application.__traces__.get_trace(tracetype, tracename, gt)

if __name__ == '__main__' :
	handler_set = [
		(r"/$", InterfaceHandler),
		(r"/([a-z0-9\.\-]+\.js)$", JSHandler),
		(r"/trace$", TraceListHandler),
		(r"/trace/([a-z0-9\.\-_]+)/([a-z0-9\.\-_]+)/([0-9]+)$", TraceHandler)
	]

	sock = zmqsub.JSONZMQSub(sys.argv[1])
	tt = TraceThread(sock)
	tt.start()
	traces = tt

	application = tornado.web.Application(handler_set)
	application.__traces__ = traces
	application.__interface__ = open('interface.html').read()

	application.listen(8008)

	application.__io_instance__ = tornado.ioloop.IOLoop.instance()
	
	try :
		application.__io_instance__.start()
	finally :
		tt.stop()
