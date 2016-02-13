import urllib2, urllib
import xbmc
import os
from elementtree import ElementTree

def fileExists(f): return os.access(f, os.F_OK)

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
				return child.text
		return None

	def SetValue(self, key, value):
		#Update value in file
		found = False
		root = self.__tree.getroot()
		for child in root:
			if child.attrib['id'] == key:
				child.text = value
				break
		if not found:
			e = ElementTree.Element('value', {'id':key})
			e.text = value
			root.append(e)
		self.__tree.write(self.__configFile)

class App:
	def GetLocalConfig(self): return _config
	def GetId(self): return 'plexee.plexforboxee'

class Http(object):
	def __init__(self):
		self.opener = urllib2.build_opener(urllib2.HTTPHandler)
		self.headers = dict()
		self.code = 0

	def GetHttpResponseCode(self):
		return self.code

	def Get(self, url):
		print('MC: GET %s' % url)
		request = urllib2.Request(url)
		for p in self.headers:
			request.add_header(p, self.headers[p])
		try:
			resp = self.opener.open(request)
			self.code = resp.code
			return resp.read()
		except urllib2.HTTPError, e:
			self.code = e.code
			print('MC: POST error %d' % e.code)
			if e.code == 201:
				return e.read()
			return None

	def Reset(self):
		self.code = 0
		self.headers.clear()

	def Post(self, url, data):
		print('MC: POST %s' % url)
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
			print('MC: POST error %d' % e.code)
			if e.code == 201:
				return e.read()
			return None

	def SetHttpHeader(self, prop, value):
		self.headers[prop] = value

def GetInfoString(prop):
	if prop == "System.BuildVersion":
		return 1

def GetDeviceId(): return "123"

def GetApp(): return _app

def LogInfo(msg): print('LogInfo: %s' % msg)
def LogError(msg): print('LogError: %s' % msg)
def LogDebug(msg): print('LogDebug: %s' % msg)

_app = App()
_config = Config(os.path.join(xbmc.translatePath('special://profile'),'apps',GetApp().GetId(),'registry.xml'))
