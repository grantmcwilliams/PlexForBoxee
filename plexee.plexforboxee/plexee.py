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

class PlexeeManager(object):
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
		self.myplex = MyPlexService()

	def clearConnectionErrors(self):
		self.connectionErrors = []
		self.connectionErrorPos = 0
		
	def addConnectionError(self, msg):
		self.connectionErrors.append(msg)

	def getNextConnectionError(self):
		if self.connectionErrorPos > len(self.connectionErrors)-1:
			self.connectionErrorPos = 0
		msg = self.connectionErrors[self.connectionErrorPos]
		self.connectionErrorPos = self.connectionErrorPos + 1
		return msg

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
		self.myplex = MyPlexService()


	def getMyLibrary(self):
		libraryListItems = mc.ListItems()
		for machineID in self.myServers:
			server = self.myServers[machineID]
			windowInformation = server.getListItems(server.getLibraryUrl())
			for childListItem in windowInformation.childListItems: libraryListItems.append(childListItem)
		return libraryListItems

	def getSharedLibraries(self):
		libraryListItems = mc.ListItems()
		for machineID in self.sharedServers:
			server = self.sharedServers[machineID]
			windowInformation = server.getListItems(server.getLibraryUrl())
			for childListItem in windowInformation.childListItems: libraryListItems.append(childListItem)
		return libraryListItems

	def getMyChannels(self):
		libraryListItems = mc.ListItems()
		for machineID in self.myServers:
			server = self.myServers[machineID]
			windowInformation = server.getListItems(server.getChannelUrl())
			for childListItem in windowInformation.childListItems: libraryListItems.append(childListItem)
		return libraryListItems

	def getMyRecentlyAdded(self):
		libraryListItems = mc.ListItems()
		for	machineID in self.myServers:
			server = self.myServers[machineID]
			windowInformation = server.getListItems(server.getRecentlyAddedUrl())
			for childListItem in windowInformation.childListItems: libraryListItems.append(childListItem)
		return libraryListItems

	def getMyOnDeck(self):
		libraryListItems = mc.ListItems()
		for	machineID in self.myServers:
			server = self.myServers[machineID]
			windowInformation = server.getListItems(server.getOnDeckUrl())
			for childListItem in windowInformation.childListItems: libraryListItems.append(childListItem)
		return libraryListItems

	def getListItems(self, machineIdentifier, fullUrl):
		server = self.getServer(machineIdentifier)
		if server: return server.getListItems(fullUrl)

	def playVideoUrl(self, machineIdentifier, fullUrl, mediaIndex = 0, subtitleIndex = 0, audioIndex = 0, offset=0):
		server = self.getServer(machineIdentifier)
		if server: server.playVideoUrl(fullUrl, mediaIndex, subtitleIndex, audioIndex, offset)

	def playMusicUrl(self, machineIdentifier, fullUrl):
		server = self.getServer(machineIdentifier)
		if server: server.playMusicUrl(fullUrl)

	def getPhotoList(self, listItem):
		machineIdentifier = listItem.GetProperty("machineidentifier")
		server = self.getServer(machineIdentifier)
		if server: return server.getPhotoList(listItem)

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
				if foundServer:
					return self.ERR_MPLEX_CONNECT_FAILED
				else:
					return self.ERR_NO_MYPLEX_SERVERS
				
			self.addMyServers(myPlexServers)
			self.addSharedServers(myPlexRemote)
			return 0
		else:
			return self.ERR_MYPLEX_NOT_AUTHENTICATED

"""
Provides an interface to the MyPlex service
"""			
class MyPlexService(object):
	AUTH_URL = "https://my.plexapp.com/users/sign_in.xml"
	LIBRARY_URL = "https://my.plexapp.com/pms/system/library/sections?auth_token=%s"

	def __init__(self, username = None, password = None):
		self.username = None
		self.password = None
		self.authenticationToken = None

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
	def buildPlexCommand(self):
		http = mc.Http()
		http.SetHttpHeader("X-Plex-Platform", "Boxee")
		http.SetHttpHeader("X-Plex-Platform-Version", mc.GetInfoString("System.BuildVersion"))
		http.SetHttpHeader("X-Plex-Provides", "player")
		http.SetHttpHeader("X-Plex-Product", "Plexee")
		http.SetHttpHeader("X-Plex-Version", "1.0")
		try:http.SetHttpHeader("X-Plex-Device", mc.GetPlatform())
		except:http.SetHttpHeader("X-Plex-Device", "Boxee")
		try: http.SetHttpHeader("X-Plex-Client-Identifier", mc.GetDeviceId())
		except: http.SetHttpHeader("X-Plex-Client-Identifier", str(uuid.getnode()))
		return http
	
	def updateToken(self):
		http = self.buildPlexCommand()
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

	def getLibraryUrl(self):
		if self.authenticationToken:
			return MyPlexService.LIBRARY_URL % self.authenticationToken
		else:
			return None

	def getServers(self):
		localServers = dict()
		remoteServers = dict()

		foundServer = False
		
		if self.isAuthenticated():
			data = mc.Http().Get(self.getLibraryUrl())
			if data:
				tree = ElementTree.fromstring(data)
				for child in tree:
					host = child.attrib.get("address", "")
					port = child.attrib.get("port", "")
					accessToken = child.attrib.get("accessToken", "")
					machineIdentifier = child.attrib.get("machineIdentifier", "")
					local = child.attrib.get("owned", "0")

					util.logInfo("MyPlex found %s:%s" % (host,port))
					foundServer = True
					server = PlexServer(host, port, accessToken)
					if not server.isAuthenticated():
						continue
					if local == "1":
						localServers[machineIdentifier] = server
					else:
						remoteServers[machineIdentifier] = server
		
		return localServers, remoteServers, foundServer

"""
Provides an interface to a Plex server
"""
class PlexServer(object):
	CHANNEL_URL = "/channels/all"
	LIBRARY_URL = "/library/sections"
	RECENTLY_ADDED_URL = "/library/recentlyAdded"
	ON_DECK_URL = "/library/onDeck"
	PHOTO_TRANSCODE_URL = "/photo/:/transcode"
	STUDIO_URL = "/system/bundle/media/flags/studio/"
	RATING_URL = "/system/bundle/media/flags/contentRating/"

	THUMB_WIDTH = 400
	THUMB_HEIGHT = 225

	ART_WIDTH = 1280
	ART_HEIGHT = 720

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
		data = mc.Http().Get(self.getRootUrl())
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

	def _getTags(self, element, subElementName, attributeName, items = 0):
		result = ""
		notFirst = 0
		count = 0
		for node in element.findall(subElementName):
			count = count + 1
			if items != 0 and items < count:
				break
			if notFirst:
				result = result + ", "
			val = node.attrib.get(attributeName, "")
			if val != "":
				notFirst = 1
				result = result + val
		return result
	
	"""
	Get the additional media data for a plex media item
	Used by Play screen
	"""
	def getVideoItem(self, listItem):
		li = mc.ListItem(mc.ListItem.MEDIA_UNKNOWN)
		copyAttribs = ["type","viewGroup","itemtype","machineidentifier","thumb","art","key"]
		
		#Copy key attributes
		for a in copyAttribs:
			li.SetProperty(a, listItem.GetProperty(a))
		li.SetPath(listItem.GetPath())

		#Get video detail from plex
		data = mc.Http().Get(listItem.GetPath())
		if not data:
			return listItem
		
		tree = ElementTree.fromstring(data)[0]
		#Set video specific
		generalAttribs = ['title','audioChannels','thumb','art','contentRating','year','summary','viewOffset','duration','rating','tagline']
		episodeAttribs = ['grandparentTitle','index','parentIndex','leafCount','viewedLeafCount']
		for a in (generalAttribs + episodeAttribs):
			if tree.attrib.has_key(a):
				li.SetProperty(a.lower(), util.cleanString(tree.attrib[a]))
	
		#Set episode titles
		if li.GetProperty('type') == 'episode':
			epTitle = util.formatEpisodeTitle(season=li.GetProperty('parentindex'), episode=li.GetProperty('index'), title=li.GetProperty('title'))
			#Set tagline to episode title
			li.SetProperty('tagline',epTitle)
			#set showtitle
			li.SetProperty('title',li.GetProperty('grandparenttitle'))
	
		#Set images
		art = li.GetProperty("art")
		thumb = li.GetProperty("thumb")
		if thumb != "":
			li.SetImage(0, self.getThumbUrl(thumb, 450, 500))
		if art != "":
			li.SetImage(1, self.getThumbUrl(art, 980, 580))
		
	
		#Resolution
		mediaNode = tree.find("Media")
		if mediaNode:
			li.SetProperty("resolution",util.getResolution(mediaNode))
			
			channels = mediaNode.attrib.get("audioChannels","")
			if channels.isdigit():
				channels = int(channels)
				if channels > 2:
					channels = str(channels - 1) + ".1 channels"
				else:
					channels = str(channels) + " channels"
				li.SetProperty("channels",util.cleanString(channels))
		
		#Genre
		li.SetProperty("genre", util.cleanString(self._getTags(tree, "Genre", "tag", 2)))
		#Director
		li.SetProperty("director", util.cleanString(self._getTags(tree, "Director", "tag")))
		#Writer
		li.SetProperty("writer", util.cleanString(self._getTags(tree, "Writer", "tag")))
		#Actors
		li.SetProperty("actors", util.cleanString(self._getTags(tree, "Role", "tag")))
		
		#Duration
		duration = ""
		if tree.attrib.has_key("duration") and tree.attrib["duration"].isdigit():
			#Format millisecond duration
			duration = util.msToFormattedDuration(int(tree.attrib["duration"]))
		li.SetProperty("durationformatted", duration)

		if tree.attrib.has_key("rating"):
			li.SetProperty("roundedrating", str(int(round(float(tree.attrib["rating"])))))	
	
		return li
		
	"""
	Create list items from the plex URL to display
	"""
	def _createListItem(self, element, fullUrl):
		# Important Properties
		listItem = mc.ListItem(mc.ListItem.MEDIA_UNKNOWN)
		listItem.SetProperty("itemtype", element.tag)
		listItem.SetProperty("machineidentifier", util.cleanString(self.machineIdentifier))
		if element.attrib.has_key("key"):
			listItem.SetPath(self.getUrl(fullUrl, element.attrib["key"]))
	
		attribs = ['viewGroup','title','key','thumb','type','title1','title2','size','index','search','secondary','parentKey']
		for attribute in attribs:
			if element.attrib.has_key(attribute):
				#util.logDebug('Property [%s]=[%s]' % (attribute.lower(), util.cleanString(element.attrib[attribute])))
				listItem.SetProperty(attribute.lower(), util.cleanString(element.attrib[attribute]))

		#Special titles
		if listItem.GetProperty('type') == 'episode':
			epTitle = util.formatEpisodeTitle(season="", episode=listItem.GetProperty('index'), title=listItem.GetProperty('title'))
			listItem.SetProperty("title",epTitle)
		
		if listItem.GetProperty('type') == 'track':
			#Duration
			duration = ""
			if element.attrib.has_key("duration") and element.attrib["duration"].isdigit():
				#Format millisecond duration
				duration = util.msToFormattedDuration(int(element.attrib["duration"]),False)
			listItem.SetProperty("durationformatted", duration)
		
		# Image paths
		if element.attrib.has_key("thumb"):
			listItem.SetImage(0, self.getThumbUrl(listItem.GetProperty("thumb"), self.THUMB_WIDTH, self.THUMB_HEIGHT))
			
		return listItem

 	def isAuthenticated(self):
		return self.machineIdentifier != None

	def getUrl(self, baseUrl, key, args = None):
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
		if args: url_query = dict(cgi.parse_qsl(url_parts[4]) + args.items())
		else: url_query = dict(cgi.parse_qsl(url_parts[4]))
		if self.accessToken: url_query["X-Plex-Token"] = self.accessToken

		url_parts[4] = urllib.urlencode(url_query)

		url = urlparse.urlunparse(url_parts)
		return url

	def getListItems(self, fullUrl):
		data = mc.Http().Get(fullUrl)
		if data:
			tree = ElementTree.fromstring(data)
			titleListItem = self._createListItem(tree, fullUrl)
			titleListItem.SetProperty("plexeeview", "grid")
			
			#Set title item art/thumb to display if needed
			titleListItem.SetProperty("art", tree.attrib.get("art",""))
			titleListItem.SetProperty("thumb", tree.attrib.get("thumb",""))
			
			titleListItems = mc.ListItems()
			titleListItems.append(titleListItem)

			childListItems = mc.ListItems()
			for child in tree:
				childListItem = self._createListItem(child, fullUrl)
				childListItems.append(childListItem)

			return WindowInformation(titleListItems, childListItems)
		else:
			return None

	def getMediaOptions(self, fullUrl, mediaIndex = 0):
		"""
		Return list of media and the audio and subtitles for the mediaIndex
		Jinxo: Only the default - and any SRT files are supported at present
		"""
		util.logDebug("Loading media details for: " + fullUrl)
		subtitleItems = mc.ListItems()
		subItem = mc.ListItem(mc.ListItem.MEDIA_UNKNOWN)
		subItem.SetLabel("None")
		subItem.SetPath("")
		subtitleItems.append(subItem)

		audioItems = mc.ListItems()
		mediaItems = mc.ListItems()
		
		videoUrl = self.getUrl(self.getRootUrl(), fullUrl)
		data = mc.Http().Get(videoUrl)
		if data:
			tree = ElementTree.fromstring(data)
			videoNode = tree[0]
			foundDefault = False
			media = videoNode.findall("Media")
			
			index = 0
			for m in media:
				mediaItem = mc.ListItem(mc.ListItem.MEDIA_UNKNOWN)
				resolution = util.getResolution(m)
				audioCodec = m.attrib.get("audioCodec","")
				width = m.attrib.get("width","")
				height = m.attrib.get("height","")
				label = resolution + " (" + audioCodec.upper() + ") - " + width + "x" + height
				util.logDebug("-->Media found: " + label)
				mediaItem.SetLabel(label.encode('utf-8'))
				mediaItems.append(mediaItem)
			
			mediaNode = media[mediaIndex]
			for stream in mediaNode.find("Part").findall("Stream"):
				streamType = stream.attrib.get("streamType","0")
				language = stream.attrib.get("language","Unknown")
				format = stream.attrib.get("format","?")
				codec = stream.attrib.get("codec","?")
				path = stream.attrib.get("key","")
				id = stream.attrib.get("id","")

				if streamType == "3":
					#Subtitle
					subItem = mc.ListItem(mc.ListItem.MEDIA_UNKNOWN)
					subItem.SetProperty('id',id)
					source = "File"
					if path != "":
						subItem.SetPath(self.getUrl(self.getRootUrl(), path))
					else:
						#Jinxo: Only default supported at the moment, as I haven't been able to switch to another....
						source = "Embedded"
						default = stream.attrib.get("default","")
						if default == "":
							continue
						if foundDefault:
							continue
						foundDefault = True
						#Jinxo: The value doesn't matter - just enter something
						subItem.SetPath("1")
						
					label = language + " (" + format.upper() + ":" + source + ")"
					util.logDebug("-->Subtitle found: " + label)
					subItem.SetLabel(label.encode('utf-8'))
					subtitleItems.append(subItem)

				elif streamType == "2":
					#Audio
					audioItem = mc.ListItem(mc.ListItem.MEDIA_UNKNOWN)
					audioItem.SetPath("1")
					audioItem.SetProperty('id',id)
					label = language + " (" + codec.upper() + ")"
					util.logDebug("-->Audio found: " + label)
					audioItem.SetLabel(label.encode('utf-8'))
					audioItems.append(audioItem)
					
				else:
					continue
			
		return MediaOptions(mediaItems, subtitleItems, audioItems);
	
	"""
	Update media played position for onDeck and resuming behaviour
	An item will be added to the deck by plex based on this call
	"""
	def setMediaPlayedPosition(self, mediaKey, positionMsec):
		url = self.getRootUrl() + ":/progress?key="+mediaKey+"&identifier=com.plexapp.plugins.library&time="+str(positionMsec)
		util.logDebug("Setting media key=[%s] to position=[%s]" % (mediaKey,str(positionMsec)))
		mc.Http().Get(url)
	
	"""
	Set media as watched
	Removes from deck
	"""
	def setMediaWatched(self, mediaKey):
		url = self.getRootUrl() + ":/scrobble?key="+mediaKey+"&identifier=com.plexapp.plugins.library"
		util.logDebug("Setting media key=[%s] as watched" % mediaKey)
		mc.Http().Get(url)
		
	"""
	Set media as unwatched
	"""
	def setMediaUnwatched(self, mediaKey):
		url = self.getRootUrl() + ":/unscrobble?key="+mediaKey+"&identifier=com.plexapp.plugins.library"
		util.logDebug("Setting media key=[%s] as unwatched" % mediaKey)
		mc.Http().Get(url)

	def setAudioStream(self, partId, audioStreamId):
		import urllib2
		opener = urllib2.build_opener(urllib2.HTTPHandler)
		url = self.getRootUrl() + "library/parts/"+partId+"?audioStreamID="+audioStreamId
		util.logDebug("-->Setting audio stream: "+url)
		request = urllib2.Request(url)
		request.add_header('Content-Type', 'text/html')
		request.get_method = lambda: 'PUT'
		url = opener.open(request)
	
	def setSubtitleStream(self, partId, subtitleStreamId):
		import urllib2
		opener = urllib2.build_opener(urllib2.HTTPHandler)
		url = self.getRootUrl() + "library/parts/"+partId+"?subtitleStreamID="+subtitleStreamId
		util.logDebug("-->Setting subtitle stream: "+url)
		request = urllib2.Request(url)
		request.add_header('Content-Type', 'text/html')
		request.get_method = lambda: 'PUT'
		url = opener.open(request)

	def getDirectStreamUrl(self, mediaKey, mediaIndex, partIndex, offset = 0):
	
		xPlexPlatform = "Boxee"
		xPlexPlatformVersion = mc.GetInfoString("System.BuildVersion")
		xPlexProvides = "player"
		xPlexProduct = "Plexee"
		xPlexVersion = "1.0"
		xPlexDevice = "Windows"
		try: xPlexClientIdentifier = mc.GetDeviceId()
		except: xPlexClientIdentifier = str(uuid.getnode())

		url = self.getRootUrl() + "video/:/transcode/universal/"
		url = url + "start?path=http%3A%2F%2F127.0.0.1%3A32400%2Flibrary%2Fmetadata%2F" + str(mediaKey)
		url = url + "&mediaIndex=" + str(mediaIndex)
		url = url + "&partIndex=" + str(partIndex)
		url = url + "&protocol=http&offset=" + str(offset)
		#url = url + "&fastSeek=1&directPlay=0&directStream=1&videoQuality=100&videoResolution=1920x1080&maxVideoBitrate=20000&subtitleSize=100&audioBoost=100"
		url = url + "&fastSeek=1&directPlay=0&directStream=1&videoQuality=100&subtitleSize=100&audioBoost=100"
		url = url + "&X-Plex-Product=" + xPlexProduct
		url = url + "&X-Plex-Version=" + xPlexVersion
		url = url + "&X-Plex-Client-Identifier=" + xPlexClientIdentifier
		url = url + "&X-Plex-Platform=" + xPlexPlatform
		url = url + "&X-Plex-Platform-Version=" + xPlexPlatformVersion
		url = url + "&X-Plex-Device=" + xPlexDevice
		#url = url + "&X-Plex-Device-Name=" + ...
		url = url + "&Accept-Language=en"
		util.logDebug("-->Setting direct stream: "+url)
		return url
		
	"""
	Update the played progress every 5 seconds while the player is playing
	"""
	def monitorPlayback(self, key, offset, totalTimeSecs, isDirectStream):
		progress = 0
		util.logDebug("Monitoring playback to update progress...")
		#Whilst the file is playing back
		player = mc.GetPlayer()
		if isDirectStream:
			currentTimeSecs = offset
		while player.IsPlaying():
			#Get the current playback time
			if not isDirectStream:
				currentTimeSecs = int(player.GetTime())
			elif not player.IsPaused():
				#Can't get time from player - so estimate progress
				currentTimeSecs = currentTimeSecs + 5
			
			if totalTimeSecs != 0:
				progress = int(( float(currentTimeSecs) / float(totalTimeSecs)) * 100)
			else:
				progress = 0
			
			util.logDebug("-->Progress = "+str(progress) + " ("+str(currentTimeSecs)+":"+str(totalTimeSecs)+")")

			#If we are less than 95% complete, store resume time
			if progress > 0 and progress < 95:
				if offset == 0:
					#Clear it, likely start from beginning clicked
					offset = 1
					self.setMediaWatched(key)
				util.logDebug("-->Updating played duration to "+str(currentTimeSecs*1000))
				self.setMediaPlayedPosition(key, currentTimeSecs*1000)

			#Otherwise, mark as watched
			elif progress >= 95:
				self.setMediaWatched(key)
				break
			xbmc.sleep(5000)
		#If we get this far, playback has stopped
		util.logDebug("-->Playback Stopped (or at 95%)")

	def playVideoUrl(self, fullUrl,  mediaIndex, subtitleIndex, audioIndex, offset=0):
		videoUrl = self.getUrl(self.getRootUrl(), fullUrl)
		data = mc.Http().Get(videoUrl)
		isDirectStream = False
		if offset != 0:
			offset = offset/1000
			
		if data:
			tree = ElementTree.fromstring(data)
			videoNode = tree[0]
			playlist = mc.PlayList(mc.PlayList.PLAYLIST_VIDEO)
			playlist.Clear()

			thumbnailUrl = self.getThumbUrl(videoNode.attrib.get("thumb"), 100, 100)
			description = util.cleanString(videoNode.attrib.get("summary",""))
			title = util.cleanString(videoNode.attrib.get("title", "Plex Video"))
			contentRating = util.cleanString(videoNode.attrib.get("contentRating",""))
			videoId = videoNode.attrib.get("ratingKey")
			
			media = videoNode.findall("Media")
			mediaNode = media[mediaIndex]
			
			totalTimeSecs = int(mediaNode.attrib.get("duration","0"))
			if totalTimeSecs != 0:
				totalTimeSecs = totalTimeSecs/1000
			
			#Find all media parts to play e.g. CD1, CD2
			partIndex = 0
			for part in mediaNode.findall("Part"):
				partId = part.attrib.get("id")
				li = mc.ListItem(mc.ListItem.MEDIA_VIDEO_CLIP)
				li.SetTitle(title)
				li.SetLabel(title)
				if audioIndex != 0:
					util.logDebug("Changing audio stream")
					self.setAudioStream(partId, str(audioIndex))
					self.setSubtitleStream(partId, str(subtitleIndex))
					
					url = self.getDirectStreamUrl(videoId, mediaIndex, partIndex, offset)
					li.SetPath(url)
					isDirectStream = True
				else:
					li.SetPath(self.getUrl(self.getRootUrl(), part.attrib.get("key")))
				li.SetThumbnail(thumbnailUrl)
				li.SetDescription(description, False)
				li.SetContentRating(contentRating)
				
				#TV Episode extras
				mediaType = videoNode.attrib.get("type","movie")
				if mediaType == 'episode':
					li.SetTVShowTitle(util.cleanString(videoNode.attrib.get("grandparentTitle","")))
					li.SetEpisode(int(videoNode.attrib.get('index')))
					li.SetSeason(int(videoNode.attrib.get('parentIndex')))
				
				playlist.Add(li)
				partIndex = partIndex + 1

			playlist.Play(0)
			
			#ok wait for player to start
			loop = 0
			loopTimeout = 20
			util.logDebug("Waiting on player...")
			while not xbmc.Player().isPlaying():
				xbmc.sleep(1000)
				loop = loop + 1
				if loop > loopTimeout:
					break
			
			if loop <= loopTimeout:
				util.logDebug("Player started...")
			else:
				util.logDebug("Timed out waiting on Player to start - progress updating may not work...")
			
			#set any offset
			if not isDirectStream:
				#Set seek and subtitles
				if offset != 0 and audioIndex == 0:
					util.logDebug("Seeking to resume position")
					xbmc.Player().seekTime(offset)

				#Set subtitles
				subtitleKey = ""
				if subtitleIndex != 0:
					for s in mediaNode.findall("Part/Stream"):
						if s.attrib.get("id") != str(subtitleIndex):
							continue;
						subtitleKey = self.getUrl(self.getRootUrl(), s.attrib.get("key"))
					
				if subtitleKey == "":
					import os
					noSubPath = os.path.join(mc.GetApp().GetAppMediaDir(), 'media', 'no_subs.srt')
					xbmc.Player().setSubtitles(noSubPath)
				else:
					util.logInfo("Setting subtitles to: " + subtitleKey)
					xbmc.Player().setSubtitles(subtitleKey)
			
			#Set audio
			#Jinxo: Alas not supported...
			#if audioIndex != 0:
			#	xbmc.Player().setAudioStream(audioIndex)
			#	util.logInfo('Setting audio to stream #: ' + str(audioIndex))
			
			#Monitor playback and update progress to plex
			key = videoNode.attrib.get('ratingKey')
			self.monitorPlayback(key, offset, totalTimeSecs, isDirectStream)
			
		else:
			return None

	def getPlexItem(self, keyUrl):
		url = self.getUrl(self.getRootUrl(), keyUrl)
		if not url:
			return False
		data = mc.Http().Get(self.getUrl(self.getRootUrl(), url))
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
	
	def playMusicUrl(self, fullUrl):
		track = self.getPlexItem(fullUrl)
		album = self.getPlexParent(track)
		artist = self.getPlexParent(album)
		if track:				
			title = track.attrib.get("title", "Plex Track")
			playlist = mc.PlayList(mc.PlayList.PLAYLIST_MUSIC)
			playlist.Clear()

			for part in track.findall("Media/Part"):
				li = mc.ListItem(mc.ListItem.MEDIA_AUDIO_MUSIC)
				if album:
					li.SetAlbum(album.attrib.get("title"))
				if artist:
					li.SetArtist(artist.attrib.get("title"))
				li.SetTitle(title)
				li.SetLabel(title)
				li.SetPath(self.getUrl(self.getRootUrl(), part.attrib.get('key')))
				playlist.Add(li)

			playlist.Play(0)
		else:
			return None

	"""
	Return a list of all child images
	"""
	def getPhotoList(self, listItem):
		#photoUrl = self.getUrl(self.getRootUrl(), fullUrl)
		url = self.getUrl(self.getRootUrl(), listItem.GetProperty('parentKey'))
		data = mc.Http().Get(url+'/children')
		if data:
			list = mc.ListItems()
			tree = ElementTree.fromstring(data)
			for photoNode in tree.findall("Photo"):
				title = photoNode.attrib.get("title", "Plex Photo")
				key = photoNode.attrib.get('key')

				for part in photoNode.findall("Media/Part"):
					li = mc.ListItem(mc.ListItem.MEDIA_PICTURE)
					li.SetProperty('key',key)
					li.SetTitle(title)
					li.SetLabel(title)
					li.SetPath(self.getUrl(self.getRootUrl(), key))
					li.SetProperty('rotation','')
					li.SetProperty('zoom','')
					#Resize images
					li.SetImage(0, self.getThumbUrl(part.attrib.get('key'),1280,1280))
					#li.SetImage(0, self.getUrl(self.getRootUrl(), part.attrib.get('key')))
					list.append(li)

			return list
		else:
			return None

	def getRootUrl(self):
		"""
		Returns the root url of the server
		"""
		return self.getUrl("http://%s:%s" % (self.host, self.port), "/")

	def getChannelUrl(self):
		"""
		Returns the channel url of the server
		"""
		return self.getUrl(self.getRootUrl(), PlexServer.CHANNEL_URL)

	def getLibraryUrl(self):
		"""
		Returns the library url of the server
		"""
		return self.getUrl(self.getRootUrl(), PlexServer.LIBRARY_URL)

	def getRecentlyAddedUrl(self):
		"""
		Returns the recently added url
		"""
		return self.getUrl(self.getRootUrl(), PlexServer.RECENTLY_ADDED_URL)

	def getOnDeckUrl(self):
		"""
		Returns the recently added url
		"""
		return self.getUrl(self.getRootUrl(), PlexServer.ON_DECK_URL)

	def getThumbUrl(self, key, width, height):
		"""
		Returns the transcode url of an image
		"""
		args = dict()
		args["url"] = self.getUrl(self.getRootUrl(), key)
		args["width"] = width
		args["height"] = height
		return self.getUrl(self.getRootUrl(), PlexServer.PHOTO_TRANSCODE_URL, args)

	def getStudioUrl(self, studio, updatedAt):
		args = dict()
		args["t"] = updatedAt
		return self.getUrl(self.getRootUrl(), PlexServer.STUDIO_URL+studio, args)

	def getContentRatingUrl(self, rating, updatedAt):
		args = dict()
		args["t"] = updatedAt
		return self.getUrl(self.getRootUrl(), PlexServer.RATING_URL + rating, args)

class WindowInformation(object):
	def __init__(self, titleListItems, childListItems):
		self.titleListItems = titleListItems
		self.childListItems = childListItems
		
class MediaOptions(object):
	def __init__(self, mediaItems, subtitleItems, audioItems):
		self.mediaItems = mediaItems
		self.subtitleItems = subtitleItems
		self.audioItems = audioItems
		