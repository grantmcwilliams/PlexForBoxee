import base64
import cgi
import mc
import urllib
import urllib2
import urlparse
import util
import uuid
import xbmc

from elementtree import ElementTree

class PlexManager(object):
	"""
	Manages all communication from Plexee and Plex Services
	"""
	ERR_NO_MYPLEX_SERVERS=1
	ERR_MPLEX_CONNECT_FAILED=2
	ERR_MYPLEX_NOT_AUTHENTICATED=3
	
	def __init__(self):
		self.myServers = dict()
		self.connectionErrors = []
		self.connectionErrorPos = 0
		self.sharedServers = dict()
		self.myplex = MyPlexService(self)
		self.xPlexPlatform = "Boxee"
		self.xPlexPlatformVersion = mc.GetInfoString("System.BuildVersion")
		self.xPlexProvides = "player"
		self.xPlexProduct = "Plexee"
		self.xPlexVersion = "1.0"
		self.xPlexDevice = "Windows"
		try: self.xPlexClientIdentifier = mc.GetDeviceId()
		except: self.xPlexClientIdentifier = str(uuid.getnode())

	def buildPlexCommand(self):
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
		http = mc.Http()
		http.SetHttpHeader("X-Plex-Platform", self.xPlexPlatform)
		http.SetHttpHeader("X-Plex-Platform-Version", self.xPlexPlatformVersion)
		http.SetHttpHeader("X-Plex-Provides", self.xPlexProvides)
		http.SetHttpHeader("X-Plex-Product", self.xPlexProduct)
		http.SetHttpHeader("X-Plex-Version", self.xPlexVersion)
		http.SetHttpHeader("X-Plex-Device", self.xPlexDevice)
		http.SetHttpHeader("X-Plex-Client-Identifier", self.xPlexClientIdentifier)
		return http

	def addMyServerObject(self, server):
		if server.isAuthenticated():
			if self.getServer(server.machineIdentifier) is None:
				self.myServers[server.machineIdentifier] = server

	def addSharedServerObject(self, server):
		"""
		Adds server to list of known servers
		"""
		if server.isAuthenticated():
			if self.getServer(server.machineIdentifier) is None:
				self.sharedServers[server.machineIdentifier] = server

	def addSharedServers(self, serverDict):
		"""
		Adds a dictionary of server objects
		"""
		for	serverKey in serverDict:
			self.addSharedServerObject(serverDict[serverKey])

	def addMyServers(self, serverDict):
		"""
		Adds a dictionary of server objects
		"""
		for serverKey in serverDict:
			self.addMyServerObject(serverDict[serverKey])

	def addMyServer(self, host, port, accessToken = None):
		"""
		Adds server from
		"""
		server = PlexServer(host, port, accessToken)
		self.addMyServerObject(server)

	def clearState(self):
		"""
		Clears any Plex objects
		"""
		self.clearServers()
		self.clearMyPlex()

	def clearServers(self):
		"""
		Removes all servers from the manager
		"""
		self.myServers = dict()
		self.sharedServers = dict()

	def clearMyPlex(self):
		"""
		Removes myPlex information from manager
		"""
		self.myplex = MyPlexService(self)

	def getServer(self, machineIdentifier):
		"""
		Return server from machine identifier
		"""
		server = self.myServers.get(machineIdentifier, None)
		if server is None: server = self.sharedServers.get(machineIdentifier, None)
		return server

	def myPlexLogin(self, username, password):
		self.myplex.login(username, password)
		if self.myplex.isAuthenticated():
			myPlexServers, myPlexRemote, foundServer = self.myplex.getServers()
			
			if len(myPlexServers) == 0 and len(myPlexRemote) == 0:
				if not foundServer:
					return self.ERR_MPLEX_CONNECT_FAILED
				else:
					return self.ERR_NO_MYPLEX_SERVERS
				
			self.addMyServers(myPlexServers)
			self.addSharedServers(myPlexRemote)
			return 0
		else:
			return self.ERR_MYPLEX_NOT_AUTHENTICATED

class MyPlexService(object):
	"""
	Provides an interface to the MyPlex service
	"""			
	BASE_URL = "https://plex.tv"
	AUTH_URL = BASE_URL + "/users/sign_in.xml"
	LIBRARY_URL = BASE_URL + "/pms/system/library/sections?auth_token=%s"
	SERVERS_URL = BASE_URL + "/pms/servers?auth_token=%s"
	QUEUE_URL = BASE_URL + "/pms/playlists/queue/all?auth_token=%s"

	def __init__(self, manager, username = None, password = None):
		self.username = None
		self.password = None
		self.authenticationToken = None
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
	
	def updateToken(self):
		http = self.plexManager.buildPlexCommand()
		base64String = base64.encodestring("%s:%s" % (self.username, self.password)).replace('\n', '')
		http.SetHttpHeader("Authorization", "Basic %s" % base64String)

		postData = "username=%s&password=%s" % (self.username, self.password)
		data = http.Post(MyPlexService.AUTH_URL, postData)
		http.Reset()

		if data:
			tree = ElementTree.fromstring(data)
			self.authenticationToken = tree.findtext("authentication-token", None)
			util.logDebug("Authentication Token set: "+self.authenticationToken)

	def isAuthenticated(self):
		return self.authenticationToken != None

	def getQueueLinkData(self, key):
		url = key+"&auth_token="+self.authenticationToken
		return mc.Http().Get(url)
		
	def getQueueData(self):
		if self.authenticationToken:
			url = MyPlexService.QUEUE_URL % self.authenticationToken
			return mc.Http().Get(url)
		else:
			return None

	def getServers(self):
		localServers = dict()
		remoteServers = dict()

		foundServer = False
		
		if self.isAuthenticated():
			url = MyPlexService.SERVERS_URL % self.authenticationToken
			data = mc.Http().Get(url)
			if data:
				tree = ElementTree.fromstring(data)
				for child in tree:
					host = child.attrib.get("address", "")
					port = child.attrib.get("port", "")
					localAddresses = child.attrib.get("localAddresses", "")
					accessToken = child.attrib.get("accessToken", "")
					machineIdentifier = child.attrib.get("machineIdentifier", "")
					local = child.attrib.get("owned", "0")

					util.logInfo("MyPlex found servers %s:%s" % (host,port))
					foundServer = True
					server = PlexServer(host, port, accessToken)
					if not server.isAuthenticated():
						continue
					if local == "1":
						#Try the local addresses
						if localAddresses:
							localAddresses = localAddresses.split(',')
							util.logInfo("--> Resolving local addresses")
							resolved = False
							for addr in localAddresses:
								data = mc.Http().Get("http://"+addr+":32400")
								util.logDebug("--> Trying local address %s:32400" % addr)
								if data:
									tree = ElementTree.fromstring(data)
									localMachineIdentifier = tree.attrib.get("machineIdentifier", "")
									if localMachineIdentifier == machineIdentifier:
										util.logInfo("--> Using local address %s:32400 instead of remote address" % addr)
										server.host = addr
										server.port = "32400"
										resolved = True
										server.isLocal = True
										break
						if not resolved:
							util.logInfo("--> Using remote address unable to resolve local address" % addr)
						localServers[machineIdentifier] = server
					else:
						remoteServers[machineIdentifier] = server
		
		return localServers, remoteServers, foundServer
		

class PlexServer(object):
	"""
	Provides an interface to a Plex server
	"""
	CHANNEL_URL = "/channels/all"
	LIBRARY_URL = "/library/sections"
	SERVERS_URL = "/servers"
	RECENTLY_ADDED_URL = "/library/recentlyAdded"
	ON_DECK_URL = "/library/onDeck"
	PHOTO_TRANSCODE_URL = "/photo/:/transcode"
	STUDIO_URL = "/system/bundle/media/flags/studio/"
	RATING_URL = "/system/bundle/media/flags/contentRating/"
	SEARCH_URL = "/search"
	SEARCH_ACTOR_URL = "/search/actor"
	TRANSCODE_URL = "/video/:/transcode/universal/start"
	UNWATCHED_URL = "/:/unscrobble"
	WATCHED_URL = "/:/scrobble"

	#Transcode qualities
	QUALITY_LIST = ["320kbps","720kbps","1.5mbps","2mbps","3mbps","4mbps","8mbps","10mbps","12mbps","20mbps"]

	def __init__(self, host, port, accessToken = None):
		self.host = host
		self.port = port
		self.accessToken = accessToken
		self.isLocal = False

		self.friendlyName = None
		self.machineIdentifier = None
		self.platform = None
		self.platformVersion = None
		self.transcoderVideoBitrates = None
		self.transcoderVideoQualities = None
		self.transcoderVideoResolutions = None
		self.version = None

		self._updateSettings()

	def _updateSettings(self):
		data = mc.Http().Get(self._getRootUrl())
		if data:
			tree = ElementTree.fromstring(data)
			self.friendlyName = tree.attrib.get("friendlyName", None)
			self.machineIdentifier = tree.attrib.get("machineIdentifier", None)
			self.platform = tree.attrib.get("platform", None)
			self.platformVersion = tree.attrib.get("platformVersion", None)
			self.transcoderVideoBitrates = tree.attrib.get("transcoderVideoBitrates", None)
			self.transcoderVideoQualities = tree.attrib.get("transcoderVideoQualities", None)
			self.transcoderVideoResolutions = tree.attrib.get("transcoderVideoResolutions", None)
			self.version = tree.attrib.get("version", None)

 	def isAuthenticated(self):
		return self.machineIdentifier != None

	def getData(self, url, args = None):
		url = self.getUrl(url, args)
		util.logDebug("Retrieving data from: " + url)
		return mc.Http().Get(url), url
	
	def getUrl(self, url, args = None):
		return self._getUrl(self._getRootUrl(), url, args)
	
	def joinUrl(self, baseUrl, key, args = None):
		return self._getUrl(baseUrl, key, args)
	
	def _getUrl(self, baseUrl, key, args = None):
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
		if not self.isLocal and self.accessToken:
			if url_parts[4] != "":
				url_parts[4] = url_parts[4] + "&X-Plex-Token=" + self.accessToken
			else:
				url_parts[4] = "X-Plex-Token=" + self.accessToken
		
		url = urlparse.urlunparse(url_parts)
		return url
	
	def setMediaPlayedPosition(self, mediaKey, positionMsec):
		"""
		Update media played position for onDeck and resuming behaviour
		An item will be added to the deck by plex based on this call
		"""
		args = dict()
		args['key']=mediaKey
		args['identifier']="com.plexapp.plugins.library"
		args['time']=str(positionMsec)
		url = self.getUrl("/:/progress",args)
		util.logDebug("Setting media key=[%s] to position=[%s]" % (mediaKey,str(positionMsec)))
		mc.Http().Get(url)
	
	def setMediaWatched(self, mediaKey):
		"""
		Set media as watched
		Removes from deck
		"""
		args = dict()
		args['key']=mediaKey
		args['identifier']="com.plexapp.plugins.library"
		url = self.getUrl(PlexServer.WATCHED_URL,args)
		util.logDebug("Setting media key=[%s] as watched" % mediaKey)
		mc.Http().Get(url)
		
	def setMediaUnwatched(self, mediaKey):
		"""
		Set media as unwatched
		"""
		args = dict()
		args['key']=mediaKey
		args['identifier']="com.plexapp.plugins.library"
		url = self.getUrl(PlexServer.UNWATCHED_URL,args)
		util.logDebug("Setting media key=[%s] as unwatched" % mediaKey)
		mc.Http().Get(url)

	def setAudioStream(self, partId, audioStreamId):
		import urllib2
		opener = urllib2.build_opener(urllib2.HTTPHandler)
		args = dict()
		args['audioStreamID']=audioStreamId
		url = self.getUrl("/library/parts/"+partId, args)
		util.logDebug("-->Setting audio stream: "+url)
		request = urllib2.Request(url)
		request.add_header('Content-Type', 'text/html')
		request.get_method = lambda: 'PUT'
		url = opener.open(request)
	
	def setSubtitleStream(self, partId, subtitleStreamId):
		import urllib2
		opener = urllib2.build_opener(urllib2.HTTPHandler)
		args = dict()
		args['subtitleStreamID']=subtitleStreamId
		url = self.getUrl("/library/parts/"+partId, args)
		util.logDebug("-->Setting subtitle stream: "+url)
		request = urllib2.Request(url)
		request.add_header('Content-Type', 'text/html')
		request.get_method = lambda: 'PUT'
		url = opener.open(request)

	def getDirectStreamUrl(self, manager, mediaKey, mediaIndex, partIndex, offset = 0):
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
		
	def getTranscodeUrl(self, manager, quality, mediaKey, mediaIndex, partIndex, offset = 0):
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
		
	def getPlexItem(self, keyUrl):
		url = self.getUrl(keyUrl)
		if not url:
			return False
		data = mc.Http().Get(self.getUrl(url))
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
	
	def _getRootUrl(self):
		"""
		Returns the root url of the server
		"""
		return self._getUrl("http://%s:%s" % (self.host, self.port), "/")

	def getChannelData(self):
		"""
		Returns the channel url of the server
		"""
		return self.getData(PlexServer.CHANNEL_URL)

	def getSectionData(self, sectionId):
		"""
		Returns the section data
		"""
		return self.getData(PlexServer.LIBRARY_URL+"/"+sectionId)

	def getLibraryData(self):
		"""
		Returns the library url of the server
		"""
		return self.getData(PlexServer.LIBRARY_URL)

	def getRecentlyAddedData(self):
		"""
		Returns the recently added url
		"""
		return self.getData(PlexServer.RECENTLY_ADDED_URL)

	def getOnDeckData(self):
		"""
		Returns the recently added url
		"""
		return self.getData(PlexServer.ON_DECK_URL)

	def getSearchData(self, query):
		args = dict()
		args['query'] = query
		return self.getData(PlexServer.SEARCH_URL, args)
		
	def getSearchActorData(self, query):
		args = dict()
		args['query'] = query
		return self.getData(PlexServer.SEARCH_ACTOR_URL, args)

	def getSearchTrackData(self, query):
		args = dict()
		args['type'] = '10'
		args['query'] = query
		return self.getData(PlexServer.SEARCH_URL, args)

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
		