import base64
import cgi
import datetime
import mc
import urllib
import urlparse
import util
import uuid

from elementtree import ElementTree

class PlexeeManager(object):
	"""
	Manages all communication from Plexee and Plex Services
	"""
	def __init__(self):
		self.myServers = dict()
		self.sharedServers = dict()
		self.myplex = MyPlexService()

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

	def playVideoUrl(self, machineIdentifier, fullUrl, subitem = None):
		server = self.getServer(machineIdentifier)
		if server: server.playVideoUrl(fullUrl, subitem)

	def playMusicUrl(self, machineIdentifier, fullUrl):
		server = self.getServer(machineIdentifier)
		if server: server.playMusicUrl(fullUrl)

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
			myPlexServers, myPlexRemote = self.myplex.getServers()
			self.addMyServers(myPlexServers)
			self.addSharedServers(myPlexRemote)
		else:
			mc.ShowDialogNotification("Error logging into myPlex service")

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

	def updateToken(self):
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

		base64String = base64.encodestring("%s:%s" % (self.username, self.password)).replace('\n', '')
		http.SetHttpHeader("Authorization", "Basic %s" % base64String)

		postData = "username=%s&password=%s" % (self.username, self.password)
		data = http.Post(MyPlexService.AUTH_URL, postData)
		http.Reset()

		if data:
			tree = ElementTree.fromstring(data)
			self.authenticationToken = tree.findtext("authentication-token", None)

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

					if local == "1":
						localServers[machineIdentifier] = PlexServer(host, port, accessToken)
					else:
						remoteServers[machineIdentifier] = PlexServer(host, port, accessToken)
		return localServers, remoteServers

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
			
	def _createListItem(self, element, fullUrl):

		# Important Properties
		listItem = mc.ListItem(mc.ListItem.MEDIA_UNKNOWN)
		listItem.SetProperty("itemtype", element.tag)
		listItem.SetProperty("machineidentifier", util.cleanString(self.machineIdentifier))

		if element.attrib.has_key("key"):
			listItem.SetPath(self.getUrl(fullUrl, element.attrib["key"]))

		# Copy everything
		for attribute in element.attrib:
			#print util.cleanString(attribute), util.cleanString(element.attrib[attribute])
			listItem.SetProperty(util.cleanString(attribute).lower(), util.cleanString(element.attrib[attribute]))
		mediaType = element.attrib.get("type","movie")
		
		#title, subtitle
		if mediaType == 'episode':
			listItem.SetProperty("title",util.cleanString(element.attrib.get("grandparentTitle","")))
			listItem.SetProperty("subtitle",util.cleanString(element.attrib.get("title","")))
		else:
			listItem.SetProperty("title",util.cleanString(element.attrib.get("title","")))
			listItem.SetProperty("subtitle",util.cleanString(element.attrib.get("tagline","")))

		#Resolution
		mediaNode = element.find("Media")
		if mediaNode:
			resolution = mediaNode.attrib.get("videoResolution","")
			if resolution.isdigit():
				resolution = resolution + "p"
			else:
				resolution = resolution.upper()
			listItem.SetProperty("resolution",util.cleanString(resolution))
			
			channels = mediaNode.attrib.get("audioChannels","")
			if channels.isdigit():
				channels = int(channels)
				if channels > 2:
					channels = str(channels - 1) + ".1 channels"
				else:
					channels = str(channels) + " channels"
				listItem.SetProperty("channels",util.cleanString(channels))
		
		#Genre
		listItem.SetProperty("genre", util.cleanString(self._getTags(element, "Genre", "tag", 2)))
		#Director
		listItem.SetProperty("director", util.cleanString(self._getTags(element, "Director", "tag")))
		#Writer
		listItem.SetProperty("writer", util.cleanString(self._getTags(element, "Writer", "tag")))
		#Actors
		listItem.SetProperty("actors", util.cleanString(self._getTags(element, "Role", "tag")))
		
		#Duration
		if element.attrib.has_key("duration"):
			td = datetime.timedelta(milliseconds=int(element.attrib["duration"]))
			td = td - datetime.timedelta(microseconds=td.microseconds)
			durParts = str(td).split(':')
			duration = ""
			if durParts[0] != "0":
				duration = durParts[0] + " hr "
			if durParts[1] != "0":
				duration = duration + durParts[1] + " min"
			if duration == "" and durParts[2] != "0":
				duration = durParts[2] + " sec"
			listItem.SetProperty("durationformatted", duration)

		if element.attrib.has_key("rating"):
			listItem.SetProperty("roundedrating", str(int(round(float(element.attrib["rating"])))))

		# Image paths

		if element.attrib.has_key("thumb"):
			listItem.SetImage(0, self.getThumbUrl(element.attrib["thumb"], PlexServer.THUMB_WIDTH, PlexServer.THUMB_HEIGHT))
			#listItem.SetImage(1, self.getThumbUrl(element.attrib["thumb"], 450, 500))

		if element.attrib.has_key("art"):
			listItem.SetProperty("artpath", self.getUrl(fullUrl, element.attrib['art']))
			#listItem.SetImage(2, self.getThumbUrl(element.attrib["art"], 980, 580))
		
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
			titleListItems = mc.ListItems()
			titleListItems.append(titleListItem)

			childListItems = mc.ListItems()
			for child in tree:
				childListItem = self._createListItem(child, fullUrl)
				childListItems.append(childListItem)

			return WindowInformation(titleListItems, childListItems)
		else:
			return None

	def getSubtitles(self, fullUrl):
		"""
		Return list of subtitles
		Jinxo: Only the default - and any SRT files are supported at present
		"""
		subItems = mc.ListItems()
		subItem = mc.ListItem(mc.ListItem.MEDIA_UNKNOWN)
		subItem.SetLabel("None")
		subItem.SetPath("")
		subItems.append(subItem)

		videoUrl = self.getUrl(self.getRootUrl(), fullUrl)
		data = mc.Http().Get(videoUrl)
		if data:
			tree = ElementTree.fromstring(data)
			videoNode = tree[0]
			foundDefault = False
			for stream in videoNode.findall("Media/Part/Stream"):
				if stream.attrib.get("streamType","0") != "3":
					continue
				subItem = mc.ListItem(mc.ListItem.MEDIA_UNKNOWN)
				language = stream.attrib.get("language","Unknown")
				format = stream.attrib.get("format","?")
				path = stream.attrib.get("key","")
				
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
					subItem.SetPath("1");
					
				label = language + " (" + format.upper() + ":" + source + ")"
				subItem.SetLabel(label.encode('utf-8'))
				subItems.append(subItem)
			
		return subItems;
		
		
	def playVideoUrl(self, fullUrl, subitem = None):
		videoUrl = self.getUrl(self.getRootUrl(), fullUrl)
		data = mc.Http().Get(videoUrl)
		if data:
			tree = ElementTree.fromstring(data)
			videoNode = tree[0]
			title = videoNode.attrib.get("title", "Plex Video")
			playlist = mc.PlayList(mc.PlayList.PLAYLIST_VIDEO)
			playlist.Clear()

			#Jinxo: How much can we add
			#item = mc.ListItem(mc.ListItem.MEDIA_VIDEO_CLIP)
            #item.SetLabel(strTitle)
            #item.SetTitle(strTitle)
            #item.SetTVShowTitle(strShowTitle)
            #item.SetGenre(strGenre)
            #item.SetStudio(strStudio)
            #item.SetEpisode(intEpisode)
            #item.SetSeason(intSeason)
            #item.SetIcon(strCoverURL)
            #item.SetThumbnail(strCoverURL)
            #item.SetDescription(strDescription)
            #item.SetPath(strPath)
            #SetDuration (or get) doesn't seem to work - use a custom property
            #item.SetProperty('duration',str(intDuration))
            #item.SetContentRating(strContentRating)			
			
			#not working
			thumbnailUrl = self.getThumbUrl(videoNode.attrib.get('thumb'), 100, 100)
			
			description = videoNode.attrib.get('summary')
			contentRating = videoNode.attrib.get('contentRating')
			
			for part in videoNode.findall("Media/Part"):
				#li = mc.ListItem(mc.ListItem.MEDIA_UNKNOWN)
				li = mc.ListItem(mc.ListItem.MEDIA_VIDEO_CLIP)
				li.SetTitle(title)
				li.SetLabel(title)
				li.SetPath(self.getUrl(self.getRootUrl(), part.attrib.get('key')))
				
				#jinxo - extra details
				li.SetThumbnail(thumbnailUrl)
				#li.SetIcon(thumbnailUrl)
				#li.SetDescription(description, False)
				#li.SetProperty('duration',part.attrib.get('duration'))
				#li.SetContentRating(contentRating)
				
				playlist.Add(li)

			playlist.Play(0)
			
			#Set subtitles
			subtitleKey = ""
			if subitem != None:
				import xbmc
				import os
				xbmc.sleep(4000)
				
				subtitleKey = subitem.GetPath()
				if subtitleKey == "":
					noSubPath = os.path.join(mc.GetApp().GetAppMediaDir(), "media", "no_subs.srt")
					xbmc.Player().setSubtitles(noSubPath)
				else:
					print "Plexee: Setting subtitles to: " + subtitleKey
					xbmc.Player().setSubtitles(subtitleKey);
		else:
			return None

	def playMusicUrl(self, fullUrl):
		trackUrl = self.getUrl(self.getRootUrl(), fullUrl)
		data = mc.Http().Get(trackUrl)
		if data:
			tree = ElementTree.fromstring(data)
			trackNode = tree[0]
			title = trackNode.attrib.get("title", "Plex Track")
			playlist = mc.PlayList(mc.PlayList.PLAYLIST_MUSIC)
			playlist.Clear()

			for part in trackNode.findall("Media/Part"):
				li = mc.ListItem(mc.ListItem.MEDIA_AUDIO_MUSIC)
				li.SetTitle(title)
				li.SetLabel(title)
				li.SetPath(self.getUrl(self.getRootUrl(), part.attrib.get('key')))
				playlist.Add(li)

			playlist.Play(0)
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