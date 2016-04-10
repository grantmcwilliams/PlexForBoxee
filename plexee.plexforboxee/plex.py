## @package plex
#  Python Plex API
#
#  Provides Python API's for the Plex ecosystem
import base64
import cgi
import urllib
import urllib2
import urlparse
import util
import uuid
from elementtree import ElementTree

class PlexRequestError(Exception):
	def __init__(self, msg, code):
		self.httpCode = code
		self.msg = msg

class PlexConnectionFailedError(Exception):
	pass

##
# Manages the interaction with the Plex ecosystem
#
class PlexManager(object):
	"""
	Manages the interaction with the Plex ecosystem
	"""
	ERR_NO_MYPLEX_SERVERS=1
	#ERR_MPLEX_CONNECT_FAILED=2
	ERR_MYPLEX_NOT_AUTHENTICATED=3

	SUCCESS=4
	ERR_USER_PIN_FAILED=5
	ERR_USER_MYPLEX_OFFLINE=6
	ERR_USER_OTHER=7
	ERR_USER_NO_PIN=8

	__instance = None

	@staticmethod
	def Instance(): return PlexManager.__instance;

	def __init__(self, props):
		if not PlexManager.__instance is None:
			raise TypeError("PlexManager may only have one instance")
		self.manualServers = dict()
		self.connectionErrors = []
		self.connectionErrorPos = 0
		self.myplex = MyPlexService(self)
		self.xPlexPlatform = props['platform']
		self.xPlexPlatformVersion = props['platformversion']
		self.xPlexProvides = props['provides']
		self.xPlexProduct = props['product']
		self.xPlexVersion = props['version']
		self.xPlexDevice = props['device']
		self.xPlexClientIdentifier = props['deviceid']
		PlexManager.__instance = self

	@classmethod
	def getData(self, url, args = None):
		if not args is None:
			url = util.buildUrl(url, args)
		util.logDebug("Retrieving data from: %s" % url)
		http = util.Http()
		data = http.Get(url)
		PlexManager.handleRequestError(http)
		return data
	
	@classmethod
	def postData(self, url, postData):
		util.logDebug("Retrieving data from: %s" % url)
		http = util.Http()
		data = http.Post(url, postData)
		PlexManager.handleRequestError(http)
		return data

	@classmethod
	def handleRequestError(self, http):
		if http.code == 0 or http.ResultSuccess(): return
		errorMsg = "An error occurred retrieving data from: %s\n%s" % (http.url, http.GetResponseMsg())
		util.logError(errorMsg)
		if http.ResultConnectFailed():
			raise PlexConnectionFailedError()
		raise PlexRequestError(errorMsg, http.code)

	def putPlexCommand(self, url):
		opener = urllib2.build_opener(urllib2.HTTPHandler)
		request = urllib2.Request(url)
		request.get_method = lambda: 'PUT'
		request.add_header('Content-Type', 'text/html')
		request.add_header("X-Plex-Platform", self.xPlexPlatform)
		request.add_header("X-Plex-Platform-Version", self.xPlexPlatformVersion)
		request.add_header("X-Plex-Provides", self.xPlexProvides)
		request.add_header("X-Plex-Product", self.xPlexProduct)
		request.add_header("X-Plex-Version", self.xPlexVersion)
		request.add_header("X-Plex-Device", self.xPlexDevice)
		request.add_header("X-Plex-Client-Identifier", self.xPlexClientIdentifier)
		return opener.open(request) 
	
	def buildPlexHttpRequest(self):
		"""
		Plex Headers
		============
		X-Plex-Platform (Platform name, eg iOS, MacOSX, Android, LG, etc)
		X-Plex-Platform-Version (Operating system version, eg 4.3.1, 10.6.7, 3.2)
		X-Plex-Provides (one or more of [player, controller, server])
		X-Plex-Product (Plex application name, eg Laika, Plex Media Server, Media Link)
		X-Plex-Version (Plex application version number)
		X-Plex-Device (Device name and model number, eg iPhone3,2, Motorola XOOM, LG5200TV)
		X-Plex-Client-Identifier (UUID, serial number, or other number unique per device)
		"""
		http = util.Http()
		http.SetHttpHeader("X-Plex-Platform", self.xPlexPlatform)
		http.SetHttpHeader("X-Plex-Platform-Version", self.xPlexPlatformVersion)
		http.SetHttpHeader("X-Plex-Provides", self.xPlexProvides)
		http.SetHttpHeader("X-Plex-Product", self.xPlexProduct)
		http.SetHttpHeader("X-Plex-Version", self.xPlexVersion)
		http.SetHttpHeader("X-Plex-Device", self.xPlexDevice)
		http.SetHttpHeader("X-Plex-Client-Identifier", self.xPlexClientIdentifier)
		return http

	def addManualServer(self, host, port):
		server = PlexServer.Manual(host, port)
		server.connect()
		if server.isConnected and self.getServer(server.machineIdentifier) is None:
			self.manualServers[server.machineIdentifier] = server
		return server

	def clearState(self):
		"""
		Clears any Plex objects
		"""
		self.clearManualServers()
		self.clearMyPlex()

	def clearManualServers(self):
		"""
		Removes all servers from the manager
		"""
		self.manualServers.clear()

	def clearMyPlex(self):
		"""
		Removes myPlex information from manager
		"""
		self.myplex = MyPlexService(self)

	def getLocalUsers(self):
		return self.myplex.getLocalUsers()
	
	def getMyPlexServers(self):	return self.myplex.allServers()
	def getMyPlexRemoteServers(self): return self.myplex.remoteServers
	def getMyPlexLocalServers(self): return self.myplex.localServers
	def getLocalServers(self):
		result = self.myplex.localServers.copy()
		result.update(self.manualServers)
		return result

	def getManualServers(self): return self.manualServers

	def switchUser(self, userId, pin):
		return self.myplex.switchUser(userId, pin)
	
	def getServer(self, machineIdentifier):
		"""
		Return server from machine identifier
		"""
		server = self.getLocalServers().get(machineIdentifier, None)
		if server is None: server = self.getMyPlexRemoteServers().get(machineIdentifier, None)
		return server

	def deletePlaylist(self, server, id):
		url = server.getUrl("/playlists/"+id)
		http = self.buildPlexHttpRequest()
		http.Delete(url)
		PlexManager.handleRequestError(http)
	
	def deleteFromPlaylist(self, server, playlistId, itemId):
		#Delete - DELETE http://10.1.3.200:32400/playlists/35339/items/72
		url = server.getUrl("/playlists/%s/items/%s" % (playlistId, itemId))
		util.logDebug("Deleting playlist item: "+url)
		http = self.buildPlexHttpRequest()
		http.Delete(url)
		PlexManager.handleRequestError(http)

	def addToPlaylist(self, server, id, key):
		#PUT http://10.1.3.200:32400/playlists/35339/items?uri=library%3A%2F%2F9dbbfd79-c597-4294-a32d-edf7c2975a41%2Fitem%2F%252Flibrary%252Fmetadata%252F34980
		key = urllib.quote(key, '')
		args = dict()
		args['uri']="library:///item/%s" % key
		url = server.getUrl("/playlists/%s/items" % id, args)
		util.logDebug("Adding playlist item: "+url)
		http = self.buildPlexHttpRequest()
		http.Put(url)
		PlexManager.handleRequestError(http)
	
	def savePlaylist(self, server, name, attribs):
		http = self.buildPlexHttpRequest()
		args = dict()
		args['title']=name
		args['type']='audio'
		args['smart']='0'
		key = urllib.quote(attribs[0]['key'], '')
		args['uri']="library:///item/%s" % key
		url = server.getUrl("/playlists", args)
		util.logDebug("Saving playlist: "+url)
		
		#TODO: Retest this is true
		#Fudge post attributes (ignore=1) - otherwise a GET is done....
		data = http.Post(url,'ignore=1')
		PlexManager.handleRequestError(http)

		tree = ElementTree.fromstring(data)[0]
		ratingKey = tree.attrib.get("ratingKey","")
		util.logDebug("Rating Key: "+data)
		if ratingKey != "":
			for a in range(1,len(attribs)):
				self.addToPlaylist(server, ratingKey, attribs[a]['key'])

	def myPlexLoadServers(self):
		if not self.myplex.isAuthenticated():
			return self.ERR_MYPLEX_NOT_AUTHENTICATED
		self.myplex.loadServers()
		if not self.myplex.hasServers():
			return self.ERR_NO_MYPLEX_SERVERS
		return self.SUCCESS

	def myPlexLogin(self, username, password):
		self.myplex.login(username, password)
		return self.myplex.isAuthenticated()

##
# Encapsulates the MyPlex online service
#
class MyPlexService(object):
	BASE_URL = "https://plex.tv"
	AUTH_URL = BASE_URL + "/users/sign_in.xml"
	LIBRARY_URL = BASE_URL + "/api/system/library/sections?auth_token=%s"
	QUEUE_URL = BASE_URL + "/api/playlists/queue/all?auth_token=%s"
	GETUSERS_URL = BASE_URL + "/api/home/users?auth_token=%s"
	SWITCHUSER_URL = BASE_URL + "/api/home/users/%s/switch?pin=%s"
	USERRESOURCES_URL = BASE_URL + "/api/resources?includeHttps=1&X-Plex-Token=%s"

	def __init__(self, manager, username = None, password = None):
		self.username = None
		self.password = None
		self.authenticationToken = None
		self.userToken = None
		self.localServers = dict()
		self.remoteServers = dict()
		self.plexManager = manager

		if username and password:
			self.login(username, password)

	def login(self, username, password):
		self.username = username
		self.password = password
		self.authenticationToken = None
		self.updateToken()

	def clear(self):
		self.username = None
		self.password = None
		self.authenticationToken = None
		self.localServers.clear()
		self.remoteServers.clear()
	
	def allServers(self):
		result = self.localServers.copy()
		result.update(self.remoteServers)
		return result

	def updateToken(self):
		http = self.plexManager.buildPlexHttpRequest()
		base64String = base64.encodestring("%s:%s" % (self.username, self.password)).replace('\n', '')
		http.SetHttpHeader("Authorization", "Basic %s" % base64String)

		postData = "username=%s&password=%s" % (self.username, self.password)
		data = http.Post(MyPlexService.AUTH_URL, postData)
		PlexManager.handleRequestError(http)
		http.Reset()

		if data:
			tree = ElementTree.fromstring(data)
			self.authenticationToken = tree.findtext("authentication-token", None)
			util.logDebug("Authentication Token set: "+self.authenticationToken)

	def isAuthenticated(self):
		return self.authenticationToken != None

	def getQueueLinkData(self, key):
		url = key+"&auth_token="+self.__getUserToken()
		if not self.authenticationToken: return url, None
		data = PlexManager.getData(url)
		return data, url
		
	def getQueueData(self):
		url = MyPlexService.QUEUE_URL % self.__getUserToken()
		if not self.authenticationToken: return url, None
		data = PlexManager.getData(url)
		return data, url

	def httpGet(self, url):
		http = self.plexManager.buildPlexHttpRequest()
		http.SetHttpHeader('X-Plex-Token',self.authenticationToken)
		data = http.Get(url)
		PlexManager.handleRequestError(http)
		return data

	def httpPost(self, url, postData = ''):
		http = self.plexManager.buildPlexHttpRequest()
		http.SetHttpHeader('X-Plex-Token',self.authenticationToken)
		data = http.Post(url,postData)
		PlexManager.handleRequestError(http)
		return data

	def switchUser(self, userId, pin):
		if not self.authenticationToken: return False
		url = MyPlexService.SWITCHUSER_URL % (userId, pin)
		http = self.plexManager.buildPlexHttpRequest()
		http.SetHttpHeader('X-Plex-Token',self.authenticationToken)
		data = http.Post(url)
		if not data:
			if http.ResultUnauthorised() and pin != '':
				util.logDebug("User switch failed PIN invalid");
				return PlexManager.ERR_USER_PIN_FAILED
			util.logDebug("Error failed to access users %s HttpCode: %d" % (url, http.code));
			return PlexManager.ERR_USER_OTHER
		
		tree = ElementTree.fromstring(data)
		token = None
		for child in tree:
			if child.tag == 'authentication-token':
				token = child.text
				break
		if token is None:
			return PlexManager.ERR_USER_OTHER
		#Set usertoken
		self.userToken = token

		#reload myplex servers
		self.loadServers()

		return PlexManager.SUCCESS

	def __getUserToken(self):
		if self.userToken: return self.userToken
		return self.authenticationToken

	def getLocalUsers(self):
		if not self.authenticationToken: return None
		url = MyPlexService.GETUSERS_URL % (self.authenticationToken)
		data = PlexManager.getData(url)
		return data, url

	def hasServers(self):
		return len(self.localServers) >0 or len(self.remoteServers) > 0

	def loadServers(self):
		self.localServers.clear()
		self.remoteServers.clear()

		if not self.isAuthenticated():
			return
		
		url = MyPlexService.USERRESOURCES_URL % self.__getUserToken()
		util.logDebug("Finding servers via: "+url)
		data = util.Http().Get(url)
		if not data:
			return

		tree = ElementTree.fromstring(data)
		#Connect to servers
		for device in tree:
			#Skip devices that aren't servers
			if device.attrib.get('provides','') != 'server': continue
			server = PlexServer.MyPlex(device)
			if server.isLocal:
				self.localServers[server.machineIdentifier] = server
			else:
				self.remoteServers[server.machineIdentifier] = server

class PlexServerConnection(object):
	def __init__(self):
		self.address = None
		self.port = None
		self.protocol = None
		self.uri = None
		self.isLocal = False

##
# Encapsulates a Plex server (local or remote)
#
class PlexServer(object):
	"""
	Encapsulates a Plex server (local or remote)
	"""

	CHANNEL_URL = "/channels/all"
	LIBRARY_URL = "/library/sections"
	RECENTLY_ADDED_URL = "/library/recentlyAdded"
	ON_DECK_URL = "/library/onDeck"
	PHOTO_TRANSCODE_URL = "/photo/:/transcode"
	STUDIO_URL = "/system/bundle/media/flags/studio/"
	RATING_URL = "/system/bundle/media/flags/contentRating/"
	SEARCH_URL = "/search"
	PLAYLIST_URL = "/playlists"
	SEARCH_ACTOR_URL = "/search/actor"
	TRANSCODE_URL = "/video/:/transcode/universal/start"
	MUSIC_TRANSCODE_URL = "/music/:/transcode/generic.mp3"
	UNWATCHED_URL = "/:/unscrobble"
	WATCHED_URL = "/:/scrobble"

	#Transcode qualities
	QUALITY_LIST = ["320kbps","720kbps","1.5mbps","2mbps","3mbps","4mbps","8mbps","10mbps","12mbps","20mbps"]

	def addConnection(self):
		conn = PlexServerConnection()
		self.__connections.append(conn)
		return conn

	def connect(self):
		#If there is a local address connect to this, otherwise connect to remote address
		#connections = sorted(server['connections'], key=lambda k: k['local'], reverse=True)
		connections = self.__connections
		connected = False
		for conn in connections:
			http = util.Http()
			self.host = conn.host
			self.port = conn.port
			self.protocol = conn.protocol
			url = self.__getRootUrl()
			data = http.Get(url)
			code = http.GetHttpResponseCode()
			util.logDebug('Connecting to server: %s' % url)
			if http.ResultUnauthorised():
				util.logDebug('Unauthorised - token required: %s' % url)
				self.isTokenRequired = True
			elif http.ResultConnectFailed():
				util.logDebug('No such site: %s' % url)
			if not http.ResultSuccess(): continue
			
			util.logInfo("Connected to server: %s" % url)
			try:
				tree = ElementTree.fromstring(data)
				self.friendlyName = tree.attrib.get("friendlyName", None)
				self.machineIdentifier = tree.attrib.get("machineIdentifier", None)
				self.platform = tree.attrib.get("platform", None)
				self.platformVersion = tree.attrib.get("platformVersion", None)
				self.transcoderVideoBitrates = tree.attrib.get("transcoderVideoBitrates", None)
				self.transcoderVideoQualities = tree.attrib.get("transcoderVideoQualities", None)
				self.transcoderVideoResolutions = tree.attrib.get("transcoderVideoResolutions", None)
				self.version = tree.attrib.get("version", None)
				connected = True
				break
			except:
				#Wasn't XML data
				util.logError('Accessed server %s:%s but I was unable to process the reponse. Is the Plex server and port correct?' % (self.host, self.port))
				data = None
			else:
				util.logDebug("Error accessing server: %s return code: %s" % (url, code))
		
		if not connected:
			util.logError("Error accessing server: %s" % self.friendlyName)
		self.isConnected = connected

	@classmethod
	def MyPlex(cls, deviceXmlElement):
		device = deviceXmlElement
		server = cls()
		server.friendlyName = device.attrib.get('name')
		util.logInfo("MyPlex found server: %s" % server.friendlyName)
		server.platform = device.attrib.get('platform')
		server.platformVersion = device.attrib.get('platformVersion')
		server.machineIdentifier = device.attrib.get('clientIdentifier')
		server.accessToken = device.attrib.get('accessToken')
		server.httpsRequired = device.attrib.get('httpsRequired') == '1'
		server.appearsOffline = device.attrib.get('presence') == '0'
		server.remoteTitle = device.attrib.get('sourceTitle')
		#server.isLocal = device.attrib.get('owned') == '1'
		server.isLocal = device.attrib.get('home','') != '0'
		server.version = device.attrib.get('productVersion')
		
		for conn in device:
			if conn.tag != 'Connection': continue
			connection = server.addConnection()
			connection.host = conn.attrib.get('address')
			connection.port = conn.attrib.get('port')
			connection.protocol = conn.attrib.get('protocol')
			connection.uri = conn.attrib.get('uri')
			connection.isLocal = conn.attrib.get('local') == '1'
		return server

	@classmethod
	def Manual(cls, host, port, token = None):
		result = cls()
		result.host = host
		result.port = port
		result.accessToken = token
		result.isTokenRequired = False
		result.isLocal = False

		#Try http first
		connection = result.addConnection()
		connection.host = host
		connection.port = port
		connection.protocol = 'https'
		connection.uri = '%s://%s:%s' % (connection.protocol, connection.host, connection.port)

		#Try https second
		connection = result.addConnection()
		connection.host = host
		connection.port = port
		connection.protocol = 'http'
		connection.uri = '%s://%s:%s' % (connection.protocol, connection.host, connection.port)
		return result

	def __init__(self):
		self.accessToken = None
		self.userAccessToken = None
		self.isTokenRequired = False
		self.isLocal = False
		self.appearsOffline = False
		self.isConnected = False
		self.remoteTitle = None
		self.friendlyName = None
		self.machineIdentifier = None
		self.platform = None
		self.platformVersion = None
		self.transcoderVideoBitrates = None
		self.transcoderVideoQualities = None
		self.transcoderVideoResolutions = None
		self.version = None

		self.httpsRequired = False

		self.host = None
		self.port = None
		self.protocol = 'http'

		self.__connections = []

	def getUrl(self, url, args = None):
		return self.__getUrl(self.__getRootUrl(), url, args)
	
	def joinUrl(self, baseUrl, key, args = None):
		return self.__getUrl(baseUrl, key, args)
	
	def __getUrl(self, baseUrl, key, args = None):
		"""
		Returns a url on the server with necessary attributes from
		specified baseUrl and key
		"""
		# get url parts
		url_parts = list(urlparse.urlparse(key))
		base_parts = list(urlparse.urlparse(baseUrl))

		# get base url parts
		if url_parts[0] == "": url_parts[0] = base_parts[0]
		if url_parts[1] == "": url_parts[1] = base_parts[1]
		if url_parts[2][0] != "/": url_parts[2] = base_parts[2]+ "/" + url_parts[2]
		
		# query string
		currentArgs = dict(cgi.parse_qsl(url_parts[4]))
		if "X-Plex-Token" in currentArgs:
			del currentArgs["X-Plex-Token"]
		if args: url_query = dict(currentArgs.items() + args.items())
		else: url_query = currentArgs

		url_parts[4] = urllib.urlencode(url_query)
		accessToken = self.accessToken
		if accessToken:
			if url_parts[4] != "":
				url_parts[4] = url_parts[4] + "&X-Plex-Token=" + accessToken
			else:
				url_parts[4] = "X-Plex-Token=" + accessToken
		
		url = urlparse.urlunparse(url_parts)
		return url
	
	#ME  /:/playQueues?type=video&repeat=0&shuffle=0&includeChapters=1&uri=library%2F8eb19616-0d8b-49ab-a6c1-b7ab72878074%2Fitem%2F%2Flibrary%2Fmetadata%2F40080&X-Plex-Token=sgsfVo6jH59RtFAW4ByS
	#/playQueues?type=video&includeChapters=1&uri=library%3A%2F%2F8eb19616-0d8b-49ab-a6c1-b7ab72878074%2Fitem%2F%252Flibrary%252Fmetadata%252F40112&shuffle=0&repeat=0
	#library://8eb19616-0d8b-49ab-a6c1-b7ab72878074/item/%2Flibrary%2Fmetadata%2F40112
	def getPlayQueueId_TEST(self, videoNode):
		args = dict()
		args['type']='video'
		args['includeChapters']='1'
		args['uri']='library://%s/item/%s' % (videoNode.attrib['librarySectionUUID'],urllib.quote_plus(videoNode.attrib['key']))
		args['shuffle']='0'
		args['repeat']='0'
		http = PlexManager.Instance().buildPlexHttpRequest()
		http.SetHttpHeader('X-Plex-Token', self.userAccessToken)
		http.SetHttpHeader('X-Plex-Client-Identifier',PlexManager.Instance().xPlexClientIdentifier)
		url = self.getUrl("/playQueues",args)
		data = http.Post(url,'')
		#playQueueItemID
		if not data: return None
		for child in ElementTree.fromstring(data):
			return child.attrib.get('playQueueItemID',None)

	#/:/progress?identifier=com.plexapp.plugins.library&key=40137&time=165000&X-Plex-Token=sgsfVo6jH59RtFAW4ByS
	#/:/timeline?ratingKey=40112&key=%2Flibrary%2Fmetadata%2F40112&state=playing&playQueueItemID=3979&time=216754&duration=2544384&X-Plex-Token=sgsfVo6jH59RtFAW4ByS
	#/:/timeline?type=video&repeat=0&shuffle=0&includeChapters=1&uri=library%2F8eb19616-0d8b-49ab-a6c1-b7ab72878074%2Fitem%2F%2Flibrary%2Fmetadata%2F40080&X-Plex-Token=sgsfVo6jH59RtFAW4ByS
	#TODO: It looks like the client has to be registered for this to work
	#For users this generates an X-Plex-Client-Identifier error on the Plex Server
	#I believe because it can't find the registered client
	def setMediaPlayedPosition_TEST(self, videoNode, queueId, positionMsec):
		"""
		Update media played position for onDeck and resuming behaviour
		An item will be added to the deck by plex based on this call
		"""
		args = dict()
		args['ratingKey']=videoNode.attrib['ratingKey']
		args['key']=videoNode.attrib['key']
		args['state']='playing'
		args['playQueueItemID']=queueId
		args['time']=str(positionMsec)
		args['duration']=videoNode.attrib['duration']
		http = PlexManager.Instance().buildPlexHttpRequest()
		http.SetHttpHeader('X-Plex-Token', self.userAccessToken)
		http.SetHttpHeader('X-Plex-Client-Identifier',PlexManager.Instance().xPlexClientIdentifier)
		url = self.getUrl("/:/timeline",args)
		util.logDebug("Setting media key=[%s] to position=[%s]" % (args['ratingKey'],str(positionMsec)))
		http.Get(url)

	def setMediaPlayedPosition(self, videoNode, queueId, positionMsec):
		"""
		Update media played position for onDeck and resuming behaviour
		An item will be added to the deck by plex based on this call
		"""
		ratingKey=videoNode.attrib['ratingKey']
		key=videoNode.attrib['key']

		args = dict()
		args['key']=ratingKey
		args['identifier']="com.plexapp.plugins.library"
		args['time']=str(positionMsec)
		url = self.getUrl("/:/progress",args)
		http = PlexManager.Instance().buildPlexHttpRequest()
		util.logDebug("Setting media key=[%s] to position=[%s]" % (ratingKey,str(positionMsec)))
		util.Http().Get(url)
	
	def setMediaWatched(self, ratingKey):
		"""
		Set media as watched
		Removes from deck
		"""
		args = dict()
		args['key']=ratingKey
		args['identifier']="com.plexapp.plugins.library"
		url = self.getUrl(PlexServer.WATCHED_URL,args)
		util.logDebug("Setting media key=[%s] as watched" % ratingKey)
		util.Http().Get(url)
	
	def setMediaUnwatched(self, mediaKey):
		"""
		Set media as unwatched
		"""
		args = dict()
		args['key']=mediaKey
		args['identifier']="com.plexapp.plugins.library"
		url = self.getUrl(PlexServer.UNWATCHED_URL,args)
		util.logDebug("Setting media key=[%s] as unwatched" % mediaKey)
		util.Http().Get(url)

	def setAudioStream(self, manager, partId, audioStreamId):
		args = dict()
		args['audioStreamID']=audioStreamId
		url = self.getUrl("/library/parts/"+partId, args)
		util.logDebug("-->Setting audio stream: "+url)
		manager.putPlexCommand(url)
	
	def setSubtitleStream(self, manager, partId, subtitleStreamId):
		args = dict()
		args['subtitleStreamID']=subtitleStreamId
		url = self.getUrl("/library/parts/"+partId, args)
		util.logDebug("-->Setting subtitle stream: "+url)
		manager.putPlexCommand(url)

	def getMusicTranscodeToMp3(self, manager, mediaKey):
		args = dict()
		args['url']="http://127.0.0.1:"+str(self.port)+"/library/metadata/" + str(mediaKey)
		args['format']='mp3'
		args['audioCodec']='libmp3lame'
		args['audioBitrate']='320'
		args['audioSamples']='44100'
		args['X-Plex-Product']=manager.xPlexProduct
		args['X-Plex-Version']=manager.xPlexVersion
		args['X-Plex-Client-Identifier']=manager.xPlexClientIdentifier
		args['X-Plex-Platform']=manager.xPlexPlatform
		args['X-Plex-Platform-Version']=manager.xPlexPlatformVersion
		args['X-Plex-Device']=manager.xPlexDevice
		url = self.getUrl(PlexServer.MUSIC_TRANSCODE_URL, args)
		util.logDebug("-->Setting music stream: "+url)
		return url
		
	def getVideoDirectStreamUrl(self, manager, mediaKey, mediaIndex, partIndex, offset = 0):
		args = dict()
		args['path']="http://127.0.0.1:"+str(self.port)+"/library/metadata/" + str(mediaKey)
		args['mediaIndex']=str(mediaIndex)
		args['partIndex']=str(partIndex)
		#args['protocol']="http"
		args['protocol']="hls"
		#args['protocol']="dash"
		args['offset']=str(offset)
		args['fastSeek']="1"
		args['directPlay']="0"
		args['directStream']="1"
		args['waitForSegments']="1"
		args['videoQuality']="100"
		args['subtitleSize']="100"
		args['audioBoost']="100"
		args['X-Plex-Product']=manager.xPlexProduct
		args['X-Plex-Version']=manager.xPlexVersion
		args['X-Plex-Client-Identifier']=manager.xPlexClientIdentifier
		args['X-Plex-Platform']=manager.xPlexPlatform
		args['X-Plex-Platform-Version']=manager.xPlexPlatformVersion
		args['X-Plex-Device']=manager.xPlexDevice
		args['Accept-Language']="en"
		
		url = self.getUrl(PlexServer.TRANSCODE_URL, args)
		util.logDebug("-->Setting direct stream: "+url)
		return url
		
	def getVideoTranscodeUrl(self, manager, quality, mediaKey, mediaIndex, partIndex, offset = 0):
		args = dict()
		args['path']="http://127.0.0.1:"+str(self.port)+"/library/metadata/" + str(mediaKey)
		args['mediaIndex']=str(mediaIndex)
		args['partIndex']=str(partIndex)
		args['protocol']="http"
		#args['protocol']="hls"
		#args['protocol']="dash"
		args['offset']=str(offset)
		args['fastSeek']="1"
		args['directPlay']="0"
		args['directStream']="0"
		args['waitForSegments']="1"
		args['subtitleSize']="100"
		args['audioBoost']="100"
		args['X-Plex-Product']=manager.xPlexProduct
		args['X-Plex-Version']=manager.xPlexVersion
		args['X-Plex-Client-Identifier']=manager.xPlexClientIdentifier
		args['X-Plex-Platform']=manager.xPlexPlatform
		args['X-Plex-Platform-Version']=manager.xPlexPlatformVersion
		args['X-Plex-Device']=manager.xPlexDevice
		args['Accept-Language']="en"
		
		if quality == QUALITY_LIST[0]:
			args['videoResolution'] = "420x240"
			args['maxVideoBitrate'] = "320"
			args['videoQuality'] = "30"
		elif quality == QUALITY_LIST[1]:
			args['videoResolution'] = "576x320"
			args['maxVideoBitrate'] = "720"
			args['videoQuality'] = "40"
		elif quality == QUALITY_LIST[2]:
			args['videoResolution'] = "720x480"
			args['maxVideoBitrate'] = "1500"
			args['videoQuality'] = "60"
		elif quality == QUALITY_LIST[3]:
			args['videoResolution'] = "1024x768"
			args['maxVideoBitrate'] = "2000"
			args['videoQuality'] = "60"
		elif quality == QUALITY_LIST[4]:
			args['videoResolution'] = "1280x720"
			args['maxVideoBitrate'] = "3000"
			args['videoQuality'] = "75"
		elif quality == QUALITY_LIST[5]:
			args['videoResolution'] = "1280x720"
			args['maxVideoBitrate'] = "4000"
			args['videoQuality'] = "100"
		elif quality == QUALITY_LIST[6]:
			args['videoResolution']= "1920x1080"
			args['maxVideoBitrate'] = "8000"
			args['videoQuality'] = "60"
		elif quality == QUALITY_LIST[7]:
			args['videoResolution']= "1920x1080"
			args['maxVideoBitrate'] = "10000"
			args['videoQuality'] = "75"
		elif quality == QUALITY_LIST[8]:
			args['videoResolution']= "1920x1080"
			args['maxVideoBitrate'] = "12000"
			args['videoQuality'] = "90"
		elif quality == QUALITY_LIST[9]:
			args['videoResolution'] = "1920x1080"
			args['maxVideoBitrate'] = "20000"
			args['videoQuality'] = "100"

		url = self.getUrl(PlexServer.TRANSCODE_URL, args)
		util.logDebug("-->Setting transcode stream: "+url)
		return url
	
	def getData(self, url, args = None):
		url = self.getUrl(url, args)
		data = PlexManager.getData(url)
		return data, url
		
	def getPlexItem(self, keyUrl):
		url = self.getUrl(keyUrl)
		if not url: return False
		data = PlexManager.getData(url)
		if not data:
			return False
		tree = ElementTree.fromstring(data)
		if not tree:
			return False
		return tree[0]
	
	def getPlexParent(self, plexItem):
		if not plexItem:
			return False
		key = plexItem.attrib.get("parentKey")
		return self.getPlexItem(key)
	
	def __getRootUrl(self):
		"""
		Returns the root url of the server
		"""
		#return self.__getUrl(self.__uri, "/")
		return self.__getUrl("%s://%s:%s" % (self.protocol, self.host, self.port), "/")

	def getPlaylistData(self):
		url = self.getUrl(PlexServer.PLAYLIST_URL)
		return PlexManager.getData(url), url
	
	def getChannelData(self):
		"""
		Returns the channel url of the server
		"""
		url = self.getUrl(PlexServer.CHANNEL_URL)
		return PlexManager.getData(url), url

	def getSectionData(self, sectionId):
		"""
		Returns the section data
		"""
		url = self.getUrl(PlexServer.LIBRARY_URL+"/"+sectionId)
		return PlexManager.getData(url), url

	def getLibraryData(self):
		"""
		Returns the library data from the server
		"""
		url = self.getUrl(PlexServer.LIBRARY_URL)
		return PlexManager.getData(url), url

	def getRecentlyAddedData(self):
		"""
		Returns the recently added url
		"""
		url = self.getUrl(PlexServer.RECENTLY_ADDED_URL)
		return PlexManager.getData(url), url

	def getOnDeckData(self):
		"""
		Returns the recently added url
		"""
		url = self.getUrl(PlexServer.ON_DECK_URL)
		return PlexManager.getData(url), url

	def getSearchData(self, query):
		args = dict()
		args['query'] = query
		url = self.getUrl(PlexServer.SEARCH_URL)
		return PlexManager.getData(url, args), url
		
	def getSearchActorData(self, query):
		args = dict()
		args['query'] = query
		url = self.getUrl(PlexServer.SEARCH_ACTOR_URL)
		return PlexManager.getData(url, args), url

	def getSearchTrackData(self, query):
		args = dict()
		args['type'] = '10'
		args['query'] = query
		url = self.getUrl(PlexServer.SEARCH_URL)
		return PlexManager.getData(url, args), url

	def getThumbUrl(self, key, width, height):
		"""
		Returns the transcode url of an image
		"""
		if key == "":
			return ""
		args = dict()
		args["url"] = self.getUrl(key)
		args["width"] = width
		args["height"] = height
		return self.getUrl(PlexServer.PHOTO_TRANSCODE_URL, args)

	def getStudioUrl(self, studio, updatedAt):
		if studio == "":
			return ""
		args = dict()
		args["t"] = updatedAt
		return self.getUrl(PlexServer.STUDIO_URL + studio, args)

	def getContentRatingUrl(self, rating, updatedAt):
		if rating == "":
			return ""
		args = dict()
		args["t"] = updatedAt
		return self.getUrl(PlexServer.RATING_URL + rating, args)
		