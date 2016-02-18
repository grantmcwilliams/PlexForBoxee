import os
import mc, xbmc
import datetime
import inspect
import md5
import urllib2
import urllib
from elementtree import ElementTree

class Constants(object):
	IS_DEBUG = -1

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
		Constants.IS_DEBUG = mc.GetApp().GetLocalConfig().GetValue("debug")
		
#	msg = cleanString(msg)
	if Constants.IS_DEBUG:
		try:
			stack = inspect.stack()
			the_class = stack[1][0].f_locals["self"].__class__
			the_method = stack[1][0].f_code.co_name
			print "DEBUG Plexee: %s, %s: %s" % (the_class, the_method, str(msg))
		except:
			print("DEBUG Plexee: " + str(msg))
			#pass
	else:
		#pass
		print("DEBUG Plexee: " + str(msg))

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
	def __init__(self):
		self.opener = urllib2.build_opener(urllib2.HTTPHandler)
		self.headers = dict()
		self.code = 0

	def GetHttpResponseCode(self):
		return self.code

	def Get(self, url):
		request = urllib2.Request(url)
		for p in self.headers:
			request.add_header(p, self.headers[p])
		try:
			resp = self.opener.open(request)
			self.code = resp.code
			return resp.read()
		except urllib2.HTTPError, e:
			self.code = e.code
			if e.code == 201:
				return e.read()
			return None
		except urllib2.URLError:
			#Failed to access
			self.code = -1
			return None

	def Reset(self):
		self.code = 0
		self.headers.clear()

	def Post(self, url, data):
		request = urllib2.Request(url, data)
		for p in self.headers:
			request.add_header(p, self.headers[p])
		request.get_method = lambda: 'POST'
		try:
			resp = self.opener.open(request)
			self.code = resp.code
			return resp.read()
		except urllib2.HTTPError, e:
			self.code = e.code
			if e.code == 201:
				return e.read()
			return None

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
