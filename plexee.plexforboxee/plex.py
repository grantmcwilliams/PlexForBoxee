﻿## @package plex
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

##
# Manages the interaction with the Plex ecosystem
#
class PlexManager(object):
	"""
	Manages the interaction with the Plex ecosystem
	"""
	ERR_NO_MYPLEX_SERVERS=1
	ERR_MPLEX_CONNECT_FAILED=2
	ERR_MYPLEX_NOT_AUTHENTICATED=3
	
	def __init__(self, props):
		self.myServers = dict()
		self.connectionErrors = []
		self.connectionErrorPos = 0
		self.sharedServers = dict()
		self.myplex = MyPlexService(self)
		self.xPlexPlatform = props['platform']
		self.xPlexPlatformVersion = props['platformversion']
		self.xPlexProvides = props['provides']
		self.xPlexProduct = props['product']
		self.xPlexVersion = props['version']
		self.xPlexDevice = props['device']
		self.xPlexClientIdentifier = props['deviceid']

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
		http = util.Http()
		http.SetHttpHeader("X-Plex-Platform", self.xPlexPlatform)
		http.SetHttpHeader("X-Plex-Platform-Version", self.xPlexPlatformVersion)
		http.SetHttpHeader("X-Plex-Provides", self.xPlexProvides)
		http.SetHttpHeader("X-Plex-Product", self.xPlexProduct)
		http.SetHttpHeader("X-Plex-Version", self.xPlexVersion)
		http.SetHttpHeader("X-Plex-Device", self.xPlexDevice)
		http.SetHttpHeader("X-Plex-Client-Identifier", self.xPlexClientIdentifier)
		return http

	def addMyServerObject(self, server):
		if server.isValid():
			if self.getServer(server.machineIdentifier) is None:
				self.myServers[server.machineIdentifier] = server

	def addSharedServerObject(self, server):
		"""
		Adds server to list of known servers
		"""
		if server.isValid():
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
		return server

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

	def getLocalUsers(self):
		users = []
		for key in self.myServers:
			server = self.myServers[key]
			a = self.myplex.getLocalUsers(server)
			if not a is None:
				users.extend(a)
		return users
	
	def getServers(self):
		return self.myServers
		
	def switchUser(self, token, machineIdentifier):
		servers = self.getServers()
		for k in servers:
			server = servers[k]
			server.userAccessToken = None
			if machineIdentifier == server.machineIdentifier:
				server.userAccessToken = token
	
	def getServer(self, machineIdentifier):
		"""
		Return server from machine identifier
		"""
		server = self.myServers.get(machineIdentifier, None)
		if server is None: server = self.sharedServers.get(machineIdentifier, None)
		return server

	def deletePlaylist(self, server, id):
		url = server._getUrl(server._getRootUrl(), "/playlists/"+id)
		http = self.buildPlexCommand()
		http.Delete(url)
	
	def deleteFromPlaylist(self, server, playlistId, itemId):
		#Delete - DELETE http://10.1.3.200:32400/playlists/35339/items/72
		url = server._getUrl(server._getRootUrl(), "/playlists/%s/items/%s" % (playlistId, itemId))
		util.logDebug("Deleting playlist item: "+url)
		http = self.buildPlexCommand()
		http.Delete(url)

	def addToPlaylist(self, server, id, key):
		#PUT http://10.1.3.200:32400/playlists/35339/items?uri=library%3A%2F%2F9dbbfd79-c597-4294-a32d-edf7c2975a41%2Fitem%2F%252Flibrary%252Fmetadata%252F34980
		key = urllib.quote(key, '')
		args = dict()
		args['uri']="library:///item/%s" % key
		url = server._getUrl(server._getRootUrl(), "/playlists/%s/items" % id, args)
		util.logDebug("Adding playlist item: "+url)
		self.putPlexCommand(url)
	
	def savePlaylist(self, server, name, attribs):
		http = self.buildPlexCommand()
		args = dict()
		args['title']=name
		args['type']='audio'
		args['smart']='0'
		key = urllib.quote(attribs[0]['key'], '')
		args['uri']="library:///item/%s" % key
		url = server._getUrl(server._getRootUrl(), "/playlists", args)
		util.logDebug("Saving playlist: "+url)
		#Fudge post attributes (ignore=1) - otherwise a GET is done....
		data = http.Post(url,'ignore=1')
		if not data:
			#todo: handle error
			return
		tree = ElementTree.fromstring(data)[0]
		ratingKey = tree.attrib.get("ratingKey","")
		util.logDebug("Rating Key: "+data)
		if ratingKey != "":
			for a in range(1,len(attribs)):
				self.addToPlaylist(server, ratingKey, attribs[a]['key'])
		
		#Add - GET http://10.1.3.200:32400/playlists/35339/items?uri=library%3A%2F%2F9dbbfd79-c597-4294-a32d-edf7c2975a41%2Fitem%2F%252Flibrary%252Fmetadata%252F34980
		#DELETE http://10.1.3.200:32400/playlists/35342
		#GET http://10.1.3.200:32400/playlists?type=audio&title=Shalala+Lala&smart=0&uri=library%3A%2F%2F9dbbfd79-c597-4294-a32d-edf7c2975a41%2Fitem%2F%252Flibrary%252Fmetadata%252F34979
		#GET http://10.1.3.200:32400/playlists?type=audio&uri=library%3A%2F%2F9a35df949e05bc86d0aa792c56e3db68c0c36250%2Fitem%2Flibrary%2Fmetadata%2F34976&smart=0&title=testy
		#http://10.1.3.200:32400/playlists?type=audio&uri=library%3A%2F%2F9dbbfd79-c597-4294-a32d-edf7c2975a41%2Fitem%2Flibrary%2Fmetadata%2F34976&smart=0&title=testy
		
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

##
# Encapsulates the MyPlex online service
#
class MyPlexService(object):
	BASE_URL = "https://plex.tv"
	AUTH_URL = BASE_URL + "/users/sign_in.xml"
	LIBRARY_URL = BASE_URL + "/api/system/library/sections?auth_token=%s"
	SERVERS_URL = BASE_URL + "/api/servers?auth_token=%s"
	QUEUE_URL = BASE_URL + "/api/playlists/queue/all?auth_token=%s"
	MULTIUSER_URL = BASE_URL + "/api/home/users?auth_token=%s"
	SWITCHUSER_URL = BASE_URL + "/api/home/users/%s/switch?auth_token=%s"
	GETUSERS_URL = BASE_URL + "/servers/%s/access_tokens.xml?auth_token=%s"

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
		return util.Http().Get(url)
		
	def getQueueData(self):
		if self.authenticationToken:
			url = MyPlexService.QUEUE_URL % self.authenticationToken
			return util.Http().Get(url)
		else:
			return None

	def getMultiUserData(self):
		if self.authenticationToken:
			url = MyPlexService.MULTIUSER_URL % self.authenticationToken
			return util.Http().Get(url)
		else:
			return None

	def getLocalUsers(self, server):
		if self.authenticationToken:
			url = MyPlexService.GETUSERS_URL % (server.machineIdentifier, self.authenticationToken)
			data = util.Http().Get(url)
			if not data:
				util.logDebug("Error failed to access users %s" % url);
				return None

			userPlusData = self.getMultiUserData()
			plusTree = ElementTree.fromstring(userPlusData)
				
			tree = ElementTree.fromstring(data)
			users = []
			#Add current user
			myplex = self.plexManager.myplex
			user = dict()
			user['name'] = myplex.username
			user['id'] = '0'
			user['token'] = myplex.authenticationToken
			user['machineidentifier'] = '0'
			user['thumb'] = ''
			users.append(user)
			
			for child in tree:
				if not child.attrib.has_key("allow_sync"):
					#Skip non-user records
					continue
				user = dict()
				user['name'] = child.attrib.get("title","")
				user['id'] = child.attrib.get("id","")
				user['token'] = child.attrib.get("token","")
				user['machineidentifier'] = server.machineIdentifier
				users.append(user)
			
			for user in users:
				#try and match more information
				for c in plusTree:
					if c.attrib.get("id","") == user['id']:
						user['thumb'] = c.attrib.get("thumb","")
					elif user['id'] == '0' and c.attrib.get("username","") == user['name']:
						user['thumb'] = c.attrib.get("thumb","")
						user['id'] = c.attrib.get("id","")
			
			return users
		else:
			return None
		
	def getServers(self):
		localServers = dict()
		remoteServers = dict()

		foundServer = False
		
		if self.isAuthenticated():
			url = MyPlexService.SERVERS_URL % self.authenticationToken
			util.logDebug("Finding servers via: "+url)
			data = util.Http().Get(url)
			if not data:
				return localServers, remoteServers, foundServer

			tree = ElementTree.fromstring(data)
			for child in tree:
				host = child.attrib.get("address", "")
				port = child.attrib.get("port", "")
				localAddresses = child.attrib.get("localAddresses", "")
				accessToken = child.attrib.get("accessToken", "")
				machineIdentifier = child.attrib.get("machineIdentifier", "")
				local = child.attrib.get("owned", "0")
				sourceTitle = child.attrib.get("sourceTitle", "")

				util.logInfo("MyPlex found server %s:%s" % (host,port))
				foundServer = True
				server = None
				if local == "1":
					#Try the local addresses
					#TODO: Similiar code exists in the server and this is a bit convoluted....
					if localAddresses:
						localAddresses = localAddresses.split(',')
						util.logInfo("--> Resolving local addresses")
						resolved = False
						for addr in localAddresses:
							http = util.Http()
							util.logDebug("--> Trying local address %s:32400" % addr)
							data = http.Get("http://"+addr+":32400/?X-Plex-Token="+accessToken)
							if http.GetHttpResponseCode() == -1:
								data = http.Get("https://"+addr+":32400/?X-Plex-Token="+accessToken)
							if data:
								tree = ElementTree.fromstring(data)
								localMachineIdentifier = tree.attrib.get("machineIdentifier", "")
								if localMachineIdentifier == machineIdentifier:
									util.logInfo("--> Using local address %s:32400 instead of remote address" % addr)
									server = PlexServer(addr, "32400", accessToken)
									resolved = True
									break
						if not resolved:
							util.logInfo("--> Using remote address %s unable to resolve local address" % host)
							server = PlexServer(host, port, accessToken)

					if server is None or not server.isValid():
						continue
					localServers[machineIdentifier] = server
				else:
					#Remote server found
					server = PlexServer(host, port, accessToken, sourceTitle)
					remoteServers[machineIdentifier] = server
		
		return localServers, remoteServers, foundServer

##
# Encapsulates a Plex server (local or remote)
#
class PlexServer(object):
	"""
	Encapsulates a Plex server (local or remote)
	"""

	#TODO: Add islocal
	CHANNEL_URL = "/channels/all"
	LIBRARY_URL = "/library/sections"
	SERVERS_URL = "/servers"
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

	def __init__(self, host, port, accessToken = None, remoteTitle = None):
		self.host = host
		self.port = port
		self.accessToken = accessToken
		self.userAccessToken = None
		self.isSecure = False
		self.isTokenRequired = False

		self.isLocal = False
		self.remoteTitle = remoteTitle
		self.isMultiuser = False

		self.friendlyName = None
		self.machineIdentifier = None
		self.platform = None
		self.platformVersion = None
		self.transcoderVideoBitrates = None
		self.transcoderVideoQualities = None
		self.transcoderVideoResolutions = None
		self.version = None

		self.__getServerAttributes()
	
	def getCurrentAccessToken(self):
		if self.userAccessToken != None:
			return self.userAccessToken
		return self.accessToken
	
	def __getServerAttributes(self):
		#Try unencrypted and no access token first
		http = util.Http()
		data = http.Get("http://%s:%s" % (self.host, self.port))
		code = http.GetHttpResponseCode()
			
		if code == -1:
			#Failed to connect, either site is not available or secured
			#Try ssl
			data = http.Get("https://%s:%s" % (self.host, self.port))
			code = http.GetHttpResponseCode()

			if code != -1:
				#Looks like it's secured
				self.isSecure = True

		self.isTokenRequired = (code == 401)
		if code == 401:
			#Permission denied
			if self.getCurrentAccessToken() is None:
				util.logInfo("User access tokens are required to access this server")
				return
			data = http.Get(self.__getRootUrl())
			code = http.GetHttpResponseCode()
			if code == 401:
				#Still an issue even with a token
				util.logError("User token may not be valid - permission denied when accessing the Plex Server")
				return

		if data:
			try:
				tree = ElementTree.fromstring(data)
				self.friendlyName = tree.attrib.get("friendlyName", None)
				self.isMultiuser = tree.attrib.get("multiuser", False)
				self.machineIdentifier = tree.attrib.get("machineIdentifier", None)
				self.platform = tree.attrib.get("platform", None)
				self.platformVersion = tree.attrib.get("platformVersion", None)
				self.transcoderVideoBitrates = tree.attrib.get("transcoderVideoBitrates", None)
				self.transcoderVideoQualities = tree.attrib.get("transcoderVideoQualities", None)
				self.transcoderVideoResolutions = tree.attrib.get("transcoderVideoResolutions", None)
				self.version = tree.attrib.get("version", None)
			except:
				#Wasn't XML data
				util.logError('Accessed server %s:%s but I was unable to process the reponse. Is the Plex server and port correct?' % (self.host, self.port))
				data = None

	def isValid(self):
		return self.machineIdentifier != None

	def getData(self, url, args = None):
		url = self.getUrl(url, args)
		util.logDebug("Retrieving data from: " + url)
		http = util.Http()
		#TODO: Handle errors
		data = http.Get(url)
		if util.Http().GetHttpResponseCode() == 400:
			pass
		return data, url
	
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
		accessToken = self.getCurrentAccessToken()
		if not self.isLocal and accessToken:
			if url_parts[4] != "":
				url_parts[4] = url_parts[4] + "&X-Plex-Token=" + accessToken
			else:
				url_parts[4] = "X-Plex-Token=" + accessToken
		
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
		util.Http().Get(url)
	
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
		
	def getPlexItem(self, keyUrl):
		url = self.getUrl(keyUrl)
		if not url:
			return False
		data = util.Http().Get(self.getUrl(url))
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
		protocol = 'http'
		if self.isSecure: protocol = 'https'
		return self.__getUrl("%s://%s:%s" % (protocol, self.host, self.port), "/")

	def getPlaylistData(self):
		return self.getData(PlexServer.PLAYLIST_URL)
	
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
		Returns the library data from the server
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
		