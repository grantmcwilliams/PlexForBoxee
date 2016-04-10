import os
import mc, xbmc
import datetime
import inspect
import md5
import urllib2
import urllib
import urlparse
import cgi
from elementtree import ElementTree

class Constants(object):
	IS_DEBUG = -1

def buildUrl(url, params):
	url_parts = list(urlparse.urlparse(url))
	query = dict(cgi.parse_qsl(url_parts[4]))
	query.update(params)
	url_parts[4] = urllib.urlencode(query)
	return urlparse.urlunparse(url_parts)

def isnumber(x):
	# "Is x a number? We say it is if it has an __int__ method."
	return hasattr(x, '__int__')

def fileExists(f): return os.access(f, os.F_OK)
def fileIsReadable(f): return os.access(f, os.R_OK)
def fileIsWriteable(f): return os.access(f, os.W_OK)

def hash(string):
	return md5.new(string).hexdigest()
	
def cleanString(string):
	return string.encode("utf-8", "replace")

def getResolution(mediaNode):
	resolution = mediaNode.attrib.get("videoResolution","")
	if resolution.isdigit():
		resolution = resolution + "p"
	else:
		resolution = resolution.upper()
	return cleanString(resolution)
	
def msToResumeTime(ms):
	if ms == 0:
		return "0 sec"
		
	s = int(int(ms)/1000)
	m = 0
	h = 0
	f = ""
	if s>=60:
		m=int(s/60)
	if m>=60:
		h=int(m/60)
		f = str(h) + " hr "
	s=s-m*60
	m=m-h*60
	if m>0:
		f = f + str(m) + " min "
	if s>0:
		f = f + str(s) + " sec "
	return f
	
def msToFormattedDuration(ms, humanReadable = True):
	td = datetime.timedelta(milliseconds=ms)
	td = td - datetime.timedelta(microseconds=td.microseconds)
	durParts = str(td).split(':')

	duration = ""
	if humanReadable:
		if durParts[0] != "0":
			duration = durParts[0] + " hr "
		if durParts[1] != "0":
			duration = duration + durParts[1] + " min"
		if duration == "" and durParts[2] != "0":
			duration = durParts[2] + " sec"
	else:
		if durParts[0] != "0":
			duration = durParts[0] + ":"
		duration = duration + durParts[1].rjust(2,'0')+':'+durParts[2].rjust(2,'0')
	return duration

def logDebug(msg):
	if Constants.IS_DEBUG == -1:
		if mc.GetApp().GetLocalConfig().GetValue("debug") == '1':
			Constants.IS_DEBUG = 1
		else:
			Constants.IS_DEBUG = 0
		
#	msg = cleanString(msg)
	if Constants.IS_DEBUG == 1:
		try:
			stack = inspect.stack()
			the_class = stack[1][0].f_locals["self"].__class__
			the_method = stack[1][0].f_code.co_name
			print "DEBUG Plexee: %s, %s: %s" % (the_class, the_method, str(msg))
		except:
			try:
				print("DEBUG Plexee: " + str(msg))
			except:
				pass
	else:
		pass
		#print("DEBUG Plexee: " + str(msg))

def logInfo(msg):
#	msg = cleanString(msg)
	print("INFO  Plexee: "+str(msg))
	
def logError(msg, trace = None):
#	msg = cleanString(msg)
	print("ERROR Plexee: "+str(msg))
	if trace is not None:
		print('-'*60)
		print(trace)
		print('-'*60)

def formatEpisodeTitle(season, episode, title):
	if season == "":
		return 'E%s - %s' % (str(episode), title)
	else:
		return 'S%s:E%s - %s' % (str(season), str(episode), title)

def getIndex(listItem, list):
	result = -1
	for l in list:
		result = result + 1
		if l.GetProperty('key') == listItem.GetProperty('key'):
			return result
	return result

def getProperties(itemlist, property):
	results = []
	if type(property) is str:
		property = [property]
	
	for i in itemlist:
		vals = dict()
		for p in property:
			vals[p] = i.GetProperty(p)
		results.append(vals)	
	return results
	
class Http(object):

	HTTP_CONNECT_FAILED = -1

	HTTP_CODES = {
		-1:'CONNECTION_FAILED',
		100:'CONTINUE',
		101:'SWITCHING_PROTOCOLS',
		102:'PROCESSING',
		200:'OK',
		201:'CREATED',
		202:'ACCEPTED',
		203:'NON_AUTHORITATIVE_INFORMATION',
		204:'NO_CONTENT',
		205:'RESET_CONTENT',
		206:'PARTIAL_CONTENT',
		207:'MULTI_STATUS',
		208:'ALREADY_REPORTED',
		226:'IM_USED',
		300:'MULTIPLE_CHOICES',
		301:'MOVED_PERMANENTLY',
		302:'FOUND',
		303:'SEE_OTHER',
		304:'NOT_MODIFIED',
		305:'USE_PROXY',
		307:'TEMPORARY_REDIRECT',
		308:'PERMANENT_REDIRECT',
		400:'BAD_REQUEST',
		401:'UNAUTHORIZED',
		402:'PAYMENT_REQUIRED',
		403:'FORBIDDEN',
		404:'NOT_FOUND',
		405:'METHOD_NOT_ALLOWED',
		406:'NOT_ACCEPTABLE',
		407:'PROXY_AUTHENTICATION_REQUIRED',
		408:'REQUEST_TIMEOUT',
		409:'CONFLICT',
		410:'GONE',
		411:'LENGTH_REQUIRED',
		412:'PRECONDITION_FAILED',
		413:'REQUEST_ENTITY_TOO_LARGE',
		414:'REQUEST_URI_TOO_LONG',
		415:'UNSUPPORTED_MEDIA_TYPE',
		416:'REQUEST_RANGE_NOT_SATISFIABLE',
		417:'EXPECTATION_FAILED',
		422:'UNPROCESSABLE_ENTITY',
		423:'LOCKED',
		424:'FAILED_DEPENDENCY',
		426:'UPGRADE_REQUIRED',
		428:'PRECONDITION_REQUIRED',
		429:'TOO_MANY_REQUESTS',
		431:'REQUEST_HEADER_FIELDS_TOO_LARGE',
		500:'INTERNAL_SERVER_ERROR',
		501:'NOT_IMPLEMENTED',
		502:'BAD_GATEWAY',
		503:'SERVICE_UNAVAILABLE',
		504:'GATEWAY_TIMEOUT',
		505:'HTTP_VERSION_NOT_SUPPORTED',
		506:'VARIANT_ALSO_NEGOTIATES',
		507:'INSUFFICIENT_STORAGE',
		508:'LOOP_DETECTED',
		510:'NOT_EXTENDED',
		511:'NETWORK_AUTHENTICATION_REQUIRED'
	}

	def ResultSuccess(self): return self.code >= 200 and self.code < 300
	def ResultRedirectionRequired(self): return self.code >= 300 and self.code < 400
	def ResultClientError(self): return self.code >= 400 and self.code < 500
	def ResultServerError(self): return self.code >= 500 and self.code < 600
	def ResultUnauthorised(self): return self.code == 401
	def ResultConnectFailed(self): return self.code == Http.HTTP_CONNECT_FAILED

	def GetResponseMsg(self):
		if self.code == 0: return 'No request has been made yet'
		if self.code == Http.HTTP_CONNECT_FAILED: return 'Unable to connect to the specified server'
		if self.code == 401: return 'The Request was unauthorised'
		try:
			codeMsg = '[%s:%s]' % (Http.HTTP_CODES[self.code], self.code)
		except:
			codeMsg = '[Unknown Code:%s]' % self.code
		if self.ResultClientError(): return 'A client error occurred %s' % codeMsg
		if self.ResultServerError(): return 'A server error occurred %s' % codeMsg
		if self.ResultRedirectionRequired(): return 'A redirection is required %s' % codeMsg
		if self.ResultSuccess(): return 'Success %s' % codeMsg 
		return 'Unexpected response %s' % codeMsg

	def __init__(self):
		self.opener = urllib2.build_opener(urllib2.HTTPHandler)
		self.headers = dict()
		self.code = 0
		self.url = ''
		self.method = ''

	def GetHttpResponseCode(self):
		return self.code

	def __request(self, method, url, data = ''):
		logDebug('%s %s' % (method, url))
		self.url = url
		self.method = method
		if data != '':
			request = urllib2.Request(url, data)
		else:
			request = urllib2.Request(url)
		request.get_method = lambda: method
		for p in self.headers:
			request.add_header(p, self.headers[p])
		try:
			resp = self.opener.open(request)
			self.code = resp.code
			logDebug(self.GetResponseMsg())
			return resp.read()
		except urllib2.HTTPError, e:
			self.code = e.code
			logDebug(self.GetResponseMsg())
			if self.ResultSuccess(): return e.read()
			return None
		except urllib2.URLError:
			#Failed to access
			self.code = Http.HTTP_CONNECT_FAILED
			logDebug(self.GetResponseMsg())
			return None

	def Get(self, url): return self.__request('GET', url)
	def Put(self, url): return self.__request('PUT', url)
	def Post(self, url, data = ''): return self.__request('POST', url, data)
	def Delete(self, url): return self.__request('DELETE', url)

	def Reset(self):
		self.code = 0
		self.headers.clear()

	def SetHttpHeader(self, prop, value):
		self.headers[prop] = value

class Config:
	"""
	Alternate config to the mc config class
	Used when the mc config isn't working
	"""
	def __init__(self, filepath):
		self.__configFile = filepath
		self.__tree = None
		self.__isvalid = False
		self.__lastModified = -1
		try:
			if not fileExists(filepath):
				f = open(filepath, 'w')
				f.write('<registry/>')
				f.close()
				self.__lastModified = os.stat(filepath).st_mtime
			self.__tree = ElementTree.parse(filepath)
			self.__isvalid = True
		except IOError:
			#Error creating file.... permissions problem?
			logError("Failed to create settings file at %s" % filepath)

	def isValid(self): return self.__isvalid
	
	def GetValue(self, key):
		mt = os.stat(self.__configFile).st_mtime
		if mt != self.__lastModified:
			#File changed - reload
			self.__tree = ElementTree.parse(self.__configFile)
			self.__lastModified = mt
		for child in self.__tree.getroot():
			if child.attrib['id'] == key:
				result = child.text
				if result is None: return ''
				else: return result
		return ''

	def SetValue(self, key, value):
		#Update value in file
		found = False
		root = self.__tree.getroot()
		for child in root:
			if child.attrib['id'] == key:
				child.text = value
				found = True
				break
		if not found:
			e = ElementTree.Element('value', {'id':key})
			e.text = value
			root.append(e)
		self.__tree.write(self.__configFile)
