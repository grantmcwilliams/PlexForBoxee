import mc
import urllib
import util
import uuid
import xbmc
import plex
import time
import threading
from plexgdm import PlexGDM
from elementtree import ElementTree

class PlexeeWindow(object):
	def __init__(self, plexee):
		self.plexee = plexee
		self.initialised = False
	
	def load(self):
		util.logDebug("On load %s started" % self.getId())
		self.onLoad()
		util.logDebug("On load %s ended" % self.getId())

	def unload(self):
		util.logDebug("On unload %s started" % self.getId())
		self.onUnload()
		util.logDebug("On unload %s ended" % self.getId())

	def activate(self):
		id = self.getId()
		util.logDebug("Activate Window %s started" % id)
		mc.ActivateWindow(id)
		#Initialise links to controls
		window = mc.GetWindow(self.getId())
		self.init(window)
		#Do any actions on activation of window
		self.onActivate(window)
		util.logDebug("Activate Window %s ended" % id)

	def onActivate(self, window): pass
	def onLoad(self): pass
	def onUnload(self): pass
	def doInit(self, window): pass
	def init(self, window):
		if not self.initialised:
			self.doInit(window)
			self.initialised = True

class PlexeeDialog(PlexeeWindow):
	def close(self): xbmc.executebuiltin("Dialog.Close("+str(self.getId())+")")
	def __init__(self, plexee):	PlexeeWindow.__init__(self, plexee)
	
class PlexeeDirectoryWindow(PlexeeWindow):
	def getId(self): return Plexee.WINDOW_DIRECTORY_ID
	def __init__(self, plexee):	PlexeeWindow.__init__(self, plexee)

	def onMenuUpdated(self): pass
	def onContentUpdated(self): pass
	
	def updateMenu(self, type, server, key):
		data = ""
		url = ""
		if type == Plexee.MENU_SECTIONS:
			data, url = server.getSectionData(key)
		elif type == Plexee.MENU_DIRECT:
			data, url = server.getData(key)
		util.logDebug("Updating menu using data from url "+url)
		menuInformation = self.plexee.getListItems(server, data, url)
		self.updateMenuItems(menuInformation.childListItems)

	def updateMenuItems(self, menuItems):
		window = mc.GetWindow(self.getId())
		window.GetList(Plexee.DIRECTORY_SECONDARY_ID).SetItems(menuItems)
		self.onMenuUpdated()

	def updateContentItems(self, windowInformation):
		window = mc.GetWindow(self.getId())
		window.GetList(Plexee.DIRECTORY_TITLE_ID).SetItems(windowInformation.titleListItems)
		window.GetList(Plexee.DIRECTORY_ITEMS_ID).SetItems(windowInformation.childListItems)
		window.GetControl(Plexee.DIRECTORY_ITEMS_ID).SetFocus()
		self.onContentUpdated()
		
class PlexeeAlbumWindow(PlexeeDirectoryWindow):
	def getId(self): return Plexee.WINDOW_ALBUM_ID
	def __init__(self, plexee):	PlexeeDirectoryWindow.__init__(self, plexee)
		
class PlexeeSeasonWindow(PlexeeDirectoryWindow):
	def getId(self): return Plexee.WINDOW_SEASON_ID
	def __init__(self, plexee):	PlexeeDirectoryWindow.__init__(self, plexee)

class PlexeeHomeWindow(PlexeeWindow):
	
	def getId(self): return Plexee.WINDOW_HOME_ID

	def __init__(self, plexee):
		PlexeeWindow.__init__(self, plexee)
		
	def doInit(self, window):
		self.myLibrary = window.GetList(110)
		self.sharedLibraries = window.GetList(210)
		self.myChannels = window.GetList(310)
		self.myRecentlyAdded = window.GetList(410)
		self.myOnDeck = window.GetList(510)
		self.searchList = window.GetList(710)
		self.myQueueList = window.GetList(810)
		self.homeGroupList = window.GetControl(Plexee.HOME_GROUPLIST_ID)
		
	def searchClicked(self):
		mc.ShowDialogWait()
		try:
			config = self.plexee.config
			window = mc.GetWindow(14000)
			searchList = window.GetList(710)
			searchText = mc.ShowDialogKeyboard("Search for?", config.getLastSearch(), False)
			if searchText != "":
				config.setLastSearch(searchText)
				searchList.SetItems(self.getSearchItems(searchText))
			else:
				config.setLastSearch('')
				blankItems = mc.ListItems()
				searchList.SetItems(blankItems)
		finally:
			mc.HideDialogWait()	
	
	def refreshMyOnDeck(self):
		try:
			self.myOnDeck.SetItems(self.getMyOnDeckItems())
		except:
			pass
	
	def onLoad(self):
		self.plexee.stopTheme()
		if self.plexee.getPlayDialog().refreshOnDeck:
			self.refreshMyOnDeck()

	
	def loadContent(self):
		util.logDebug("load content started")
		self.myLibrary.SetItems(self.getMyLibraryItems())
		self.sharedLibraries.SetItems(self.getSharedLibraryItems())
		self.myChannels.SetItems(self.getMyChannelItems())
		self.myRecentlyAdded.SetItems(self.getMyRecentlyAddedItems())
		self.myOnDeck.SetItems(self.getMyOnDeckItems())
		self.myQueueList.SetItems(self.getMyQueueItems())
		
		lastSearch = self.plexee.config.getLastSearch()
		if lastSearch and lastSearch != "":
			self.searchList.SetItems(self.getSearchItems(lastSearch))
		
		self.homeGroupList.SetFocus()

	def getMyLibraryItems(self):
		"""
		Get the local Plex server library items
		e.g.
		Movies
		TV Shows
		Photos
		"""
		libraryListItems = mc.ListItems()
		manager = self.plexee.plexManager
		for machineID in manager.myServers:
			server = manager.myServers[machineID]
			data, url = server.getLibraryData()
			windowInformation = self.plexee.getListItems(server, data, url)
			for childListItem in windowInformation.childListItems: libraryListItems.append(childListItem)
		return libraryListItems

	def getSharedLibraryItems(self):
		"""
		Get any shared Plex library items
		e.g.
		Movies
		TV Shows
		Photos
		"""
		libraryListItems = mc.ListItems()
		sharedServers = self.plexee.plexManager.sharedServers
		for machineID in sharedServers:
			server = sharedServers[machineID]
			data, url = server.getLibraryData()
			windowInformation = self.plexee.getListItems(server, data, url)
			for childListItem in windowInformation.childListItems: libraryListItems.append(childListItem)
		return libraryListItems

	def getMyChannelItems(self):
		"""
		Get any local Plex server channel items
		e.g.
		Youtube
		TED
		"""
		libraryListItems = mc.ListItems()
		myServers = self.plexee.plexManager.myServers
		for machineID in myServers:
			server = myServers[machineID]
			data, url = server.getChannelData()
			windowInformation = self.plexee.getListItems(server, data, url)
			for childListItem in windowInformation.childListItems: libraryListItems.append(childListItem)
		return libraryListItems

	def getMyRecentlyAddedItems(self):
		"""
		Get the recently added items for the local Plex servers
		"""
		libraryListItems = mc.ListItems()
		myServers = self.plexee.plexManager.myServers
		for machineID in myServers:
			server = myServers[machineID]
			data, url = server.getRecentlyAddedData()
			windowInformation = self.plexee.getListItems(server, data, url)
			for childListItem in windowInformation.childListItems: libraryListItems.append(childListItem)
		return libraryListItems

	def getMyOnDeckItems(self):
		"""
		Get the on deck items for the local Plex servers
		"""
		libraryListItems = mc.ListItems()
		myServers = self.plexee.plexManager.myServers
		for machineID in myServers:
			server = myServers[machineID]
			data, url = server.getOnDeckData()
			windowInformation = self.plexee.getListItems(server, data, url)
			for childListItem in windowInformation.childListItems: libraryListItems.append(childListItem)
		return libraryListItems

	def getMyQueueItems(self):
		"""
		Get any MyPlex queue items
		"""
		libraryListItems = mc.ListItems()
		childListItems = self.plexee._createQueueItems()
		for childListItem in childListItems: libraryListItems.append(childListItem)
		return libraryListItems
			
	def getSearchItems(self, query):
		"""
		Get items from the local Plex servers matching the query string
		"""
		libraryListItems = mc.ListItems()
		
		myServers = self.plexee.plexManager.myServers
		for	machineID in myServers:
			server = myServers[machineID]
			searchData = False
			searchUrl = False
			if query.startswith('actor:'):
				searchData, searchUrl = server.getSearchActorData(query.replace('actor:',''))
			elif query.startswith('track:'):
				searchData, searchUrl = server.getSearchTrackData(query.replace('track:',''))
			else:
				searchData, searchUrl = server.getSearchData(query)
				
			windowInformation = self.plexee.getListItems(server, searchData, searchUrl)
			
			for childListItem in windowInformation.childListItems:
				#Only allow known types
				if childListItem.GetProperty('itemtype') == 'Video' or childListItem.GetProperty('itemtype') == 'Track' or childListItem.GetProperty('itemtype') == 'Directory':
					childListItem.SetProperty('title1', 'Search')
					libraryListItems.append(childListItem)
		return libraryListItems
	
class PlexeePlayDialog(PlexeeDialog):

	def getId(self): return Plexee.DIALOG_PLAY_ID

	def __init__(self, plexee):
		PlexeeDialog.__init__(self, plexee)
		self.refreshOnDeck = False
	
	def doInit(self, window):
		self.subtitleList = window.GetList(310)
		self.playButton = window.GetButton(320)
		self.audioList = window.GetList(330)
		self.mediaList = window.GetList(340)
		self.playList = window.GetList(100)
	
	def displayPlayItem(self, item, mediaOptions, fromWindowId=0):
		listItems = mc.ListItems()
		listItems.append(item)
		self.playList.SetItems(listItems)
		self.playItem = self.playList.GetItem(0)
		machineIdentifier = self.playItem.GetProperty("machineidentifier")
		self.server = self.plexee.plexManager.getServer(machineIdentifier)
		self.subtitleList.SetItems(mediaOptions.subtitleItems)
		self.audioList.SetItems(mediaOptions.audioItems)
		self.mediaList.SetItems(mediaOptions.mediaItems)
		self.currentMediaIndex = 0
		self.refreshOnDeck = False
		if len(self.mediaList.GetItems()) <= 1:
			self.mediaList.SetEnabled(False)
		else:
			self.mediaList.SetEnabled(True)

		if fromWindowId == Plexee.WINDOW_HOME_ID and self.plexee.isEpisode(item):
			themeKey = item.GetProperty("grandparenttheme")
			util.logDebug("PLAY THEME 1: "+themeKey)
			if themeKey != "":
				util.logDebug("PLAY THEME 2")
				self.plexee.playTheme(self.server.getUrl(themeKey))

	def onLoad(self):
		pass
		
	def onUnload(self):
		self.plexee.stopTheme()
	
	def play(self):
		mc.ShowDialogWait()
		#Set the play options for media, subtitles and audio
		subtitleIndex = self.subtitleList.GetFocusedItem()
		if (subtitleIndex):
			subtitleIndex = int(self.subtitleList.GetItem(subtitleIndex).GetProperty("id"))
		else:
			subtitleIndex = 0

		audioIndex = self.audioList.GetFocusedItem()
		if (audioIndex):
			audioIndex = int(self.audioList.GetItem(audioIndex).GetProperty("id"))
		else:
			audioIndex = 0

		mediaIndex = self.mediaList.GetFocusedItem()
		self.refreshOnDeck = self.plexee.playVideo(self.server, self.playItem, mediaIndex, subtitleIndex, audioIndex)

	def checkMediaSwitch(self):
		#Switched media option
		#Grap any subtitles and audio for this media
		if self.mediaList.GetFocusedItem() != self.currentMediaIndex:
			self.currentMediaIndex = self.mediaList.GetFocusedItem()
			util.logDebug("Media switched - reloading subs/audio streams")
			if self.server:
				mediaOptions = self.plexee.getMediaOptions(self.server, self.playItem, self.mediaList.GetFocusedItem())
			else:
				mediaOptions = self.plexee.getQueueMediaOptions(self.playItem, self.mediaList.GetFocusedItem())
			self.subtitleList.SetItems(mediaOptions.subtitleItems)
			self.audioList.SetItems(mediaOptions.audioItems)

class PlexeeConnectionDialog(PlexeeDialog):

	def getId(self): return Plexee.DIALOG_CONNECT_ID
	
	def __init__(self, plexee): PlexeeDialog.__init__(self, plexee)
	
	def doInit(self, window):
		self.errorLabel = window.GetLabel(300)
		self.closeButton = window.GetButton(402)
		self.nextErrorButton = window.GetControl(401)
		self.initialised = True

	def onLoad(self):
		self.connectionErrors = []
		self.connectionErrorPos = 0
		self.connect()

	def onUnload(self):
		pass

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

	def showNextError(self):
		msg = self.getNextConnectionError()
		self.errorLabel.SetLabel(msg)
		
	def updateConnectionResult(self):
		msg = self.getNextConnectionError()
		self.errorLabel.SetVisible(True)
		self.errorLabel.SetLabel(msg)
		self.closeButton.SetVisible(True)

		if len(self.connectionErrors) > 1:
			self.nextErrorButton.SetVisible(True)
			self.nextErrorButton.SetFocus()
		else:
			self.closeButton.SetFocus()

	def connect(self):
		config = self.plexee.config
		plexManager = self.plexee.plexManager
		try:
			mc.ShowDialogWait()

			#try manual server
			if config.isManualConnectOn():
				host = config.getManualHost()
				port = str(config.getManualPort())
				plexManager.addMyServer(host, port)
				if not plexManager.myServers:
					#Manual set but no server found
					self.addConnectionError("Failed to connect to plex server: "+host+":"+port+"[CR][CR]Check the server IP and port is correct.")

			#try GDM auto discovery
			if config.isAutoConnectOn():
				discoverTime = config.getDiscoveryTime()
				serverList = PlexGDM().getServers(discoverTime);
				if serverList:
					#GDM servers found
					for serverKey in serverList:
						plexManager.addMyServer(serverList[serverKey]['ip'], serverList[serverKey]['port'])
				else:
					#GDM enabled - but no servers found
					self.addConnectionError("GDM - No servers found!" + \
						"[CR]" + \
						"[CR]1. Check that GDM is enabled on your Plex Server (you may need to restart the server)." + \
						"[CR]2. Check connectivity GDM broadcasts over UDP on port 32414" + \
						"[CR]3. Try increasing the GDM response time in the settings screen" + \
						"[CR][CR]Otherwise use the Manual Server or MyPlex options in the settings screen.")

			#try MyPlex
			if config.isMyPlexConnectOn():
				username = config.getMyPlexUser()
				passsword = config.getMyPlexPassword()
				if username and passsword:
					result = plexManager.myPlexLogin(username, passsword)
					if result == plexManager.ERR_NO_MYPLEX_SERVERS:
						self.addConnectionError("No registered MyPlex servers to connect to")
					elif result == plexManager.ERR_MPLEX_CONNECT_FAILED:
						self.addConnectionError("Unable to connect to any MyPlex registered servers.[CR][CR]Please check MyPlex for the server details and check connectivity.")
					elif result == plexManager.ERR_MYPLEX_NOT_AUTHENTICATED:
						self.addConnectionError("Failed to connect to MyPlex.[CR][CR]Authentication failed - check your username and password")

			if len(self.connectionErrors) > 0:
				#An Error Occurred
				self.updateConnectionResult()
			else:
				#No errors
				self.close()
			
			self.plexee.getHomeWindow().loadContent()
		finally:
			mc.HideDialogWait()

class PlexeeSettingsDialog(PlexeeDialog):

	def getId(self): return Plexee.DIALOG_SETTINGS_ID
	
	def __init__(self, plexee): PlexeeDialog.__init__(self, plexee)
	
	def doInit(self, window):
		#connection settings
		self.discoverClients = window.GetToggleButton(100)
		self.discoverClientTime = window.GetEdit(101)
		self.manualClient = window.GetToggleButton(102)
		self.manualClientHost = window.GetEdit(103)
		self.manualClientPort = window.GetEdit(104)
		self.myPlex = window.GetToggleButton(105)
		self.myPlexUsername = window.GetEdit(106)
		self.myPlexPassword = window.GetEdit(107)
		self.photoSettingsButton = window.GetButton(43)
		#Photo Settings
		self.slideShowZoom = window.GetToggleButton(300)
		self.slideShowDelay = window.GetEdit(301)

	def onLoad(self):
		self.connectOnClose = False
		self.loadConnectSettings()
		self.loadPhotoSettings()
		
	def onUnload(self):
		pass
	
	def loadPhotoSettings(self):
		config = self.plexee.config
		self.slideShowZoom.SetSelected(config.isSlideshowZoomOn())
		self.slideShowDelay.SetText(str(config.getSlideShowDelaySec()))
	
	def showPhotoSettings(self):
		self.photoSettingsButton.SetFocus()
	
	def savePhotoSettings(self):
		config = self.plexee.config
		val = self.slideShowDelay.GetText()
		err = config.setSlideShowDelaySec(val)
		if err != "":
			mc.ShowDialogOk("Error",err);
			return
		
		if self.slideShowZoom.IsSelected():
			config.setSlideshowZoomOn()
		else:
			config.setSlideshowZoomOff()

	def close(self):
		PlexeeDialog.close(self)
		if self.connectOnClose:
			self.plexee.initPlexee()

	def loadConnectSettings(self):
		config = self.plexee.config
		if config.isAutoConnectOn(): self.discoverClients.SetSelected(True)
		self.discoverClientTime.SetText(str(config.getDiscoveryTime()))
		if config.isManualConnectOn(): self.manualClient.SetSelected(True)
		self.manualClientHost.SetText(config.getManualHost())
		self.manualClientPort.SetText(str(config.getManualPort()))
		if config.isMyPlexConnectOn(): self.myPlex.SetSelected(True)
		self.myPlexUsername.SetText(config.getMyPlexUser())
		self.myPlexPassword.SetText(config.getMyPlexPassword())

	def saveConnectSettings(self):
		config = self.plexee.config
		discoveryTime = self.discoverClientTime.GetText()
		err = config.setDiscoveryTime(discoveryTime)
		if err:
			mc.ShowDialogOk("Error", err)
			return
				
		if self.discoverClients.IsSelected():
			config.setAutoConnectOn()
		else:
			config.setAutoConnectOff()
		
		# manual clients
		if self.manualClient.IsSelected():
			config.setManualConnectOn()
			if not self.manualClientHost.GetText() or not self.manualClientPort.GetText():
				mc.ShowDialogOk("Error","You need to specify a host and port for a manual server");
				return
		else:
			config.setManualConnectOff()
			
		config.setManualHost(self.manualClientHost.GetText())
		err = config.setManualPort(self.manualClientPort.GetText())
		if err:
			mc.ShowDialogOk("Error", err)
			return
		
		#My plex
		if self.myPlex.IsSelected():
			config.setMyPlexConnectOn()
			if not self.myPlexUsername.GetText() or not self.myPlexPassword.GetText():
				mc.ShowDialogOk("Error", "You need to specify a username and password for MyPlex");
				return
		else:
			config.setMyPlexConnectOff()
		
		config.setMyPlexUser(self.myPlexUsername.GetText())
		config.setMyPlexPassword(self.myPlexPassword.GetText())
		self.connectOnClose = True

class PlexeeConfig(object):
	def __init__(self):
		self.config = mc.GetApp().GetLocalConfig()
	def _isFlagSet(self, name):
		return (self.config.GetValue(name) != "")
	def _setFlag(self, name, bool):
		if bool:
			self.config.SetValue(name,"1")
		else:
			self.config.Reset(name)
		
	def _setInt(self, name, val, friendlyName="", min="", max=""):
		if friendlyName == "":
			friendlyName = name
		err = "The %s must be a number" % friendlyName
		if min != "" and max != "":
			err = err + " between %s and %s" % (str(min), str(max))
		elif min != "":
			err = err + " equal or greater than %s" % str(min)
		else:
			err = err + " equal or less than %s" % str(max)
		
		if min == "": min = val
		if max == "": max = val
		
		if type(val) is str:
			if not val.isdigit():
				return err
			val = int(val)
		if val < min or val > max:
			return err
		self.config.SetValue(name, str(val))
		return ""
		
	def _getInt(self, name, default=""):
		val = self.config.GetValue(name)
		if not val or not val.isdigit():
			self.config.SetValue(name, str(default))
			return default
		else:
			return int(val)
	
	def isDebugOn(self): return self._isFlagSet("debug")
	def setDebugOn(self):	self._setFlag("debug", True)
	def setDebugOff(self):	self._setFlag("debug", False)

	def hasStarted(self): return self._isFlagSet("started")
	def setHasStarted(self, bool): self._setFlag("started", bool)

	def isAutoConnectOn(self): return self._isFlagSet("usediscover")
	def setAutoConnectOn(self):	self._setFlag("usediscover", True)
	def setAutoConnectOff(self):	self._setFlag("usediscover", False)

	def isManualConnectOn(self): return self._isFlagSet("usemanual")
	def setManualConnectOn(self):	self._setFlag("usemanual", True)
	def setManualConnectOff(self):	self._setFlag("usemanual", False)
	
	def getManualPort(self): return self._getInt("manualport",32400)
	def setManualPort(self, val): self._setInt("manualport",val,"Manual Port",1,65535)
	
	def getManualHost(self): return self.config.GetValue("manualhost")
	def setManualHost(self, val): self.config.SetValue("manualhost",val)
	
	def isMyPlexConnectOn(self): return self._isFlagSet("usemyplex")
	def setMyPlexConnectOn(self):	self._setFlag("usemyplex", True)
	def setMyPlexConnectOff(self):	self._setFlag("usemyplex", False)

	def isPlayingThemeOn(self): return self._isFlagSet("playingtheme")
	def setPlayingThemeOn(self): self._setFlag("playingtheme", True)
	def setPlayingThemeOff(self): self._setFlag("playingtheme", False)
	
	def getDiscoveryTime(self): return self._getInt("discovertime",1)
	def setDiscoveryTime(self, val): return self._setInt("discovertime",val,"Discovery Time",1,5)
		
	def getMyPlexUser(self): return self.config.GetValue("myplexusername")
	def setMyPlexUser(self, val): self.config.SetValue("myplexusername",val)
	
	def getMyPlexPassword(self): return self.config.GetValue("myplexpassword")
	def setMyPlexPassword(self, val): self.config.SetValue("myplexpassword",val)
		
	def getLastSearch(self): return self.config.GetValue("lastsearch")
	def setLastSearch(self, val): self.config.SetValue("lastsearch",val)

	"""Photo Settings"""
	def isSlideshowZoomOn(self): return self._isFlagSet("slideshowzoom")
	def setSlideshowZoomOn(self):	self._setFlag("slideshowzoom", True)
	def setSlideshowZoomOff(self):	self._setFlag("slideshowzoom", False)
	
	def getSlideShowDelaySec(self): return self._getInt("slideshowdelay",5)
	def setSlideShowDelaySec(self, val): return self._setInt("slideshowdelay",val,"SlideShow Delay",1,120)
	
class Plexee(object):
	"""
	Interface with Boxee system
	"""
	WINDOW_HOME_ID = 14000
	WINDOW_DIRECTORY_ID = 14001
	WINDOW_SEASON_ID = 14002
	WINDOW_ALBUM_ID = 14003

	DIALOG_CONNECT_ID = 15002
	DIALOG_PHOTO_ID = 15003
	DIALOG_EXIT_ID = 14010
	DIALOG_SETTINGS_ID = 15000
	DIALOG_PLAY_ID = 15001
	
	WINDOW_IDS = {
		"home": WINDOW_HOME_ID,
		"default": WINDOW_DIRECTORY_ID,
		"episode": WINDOW_SEASON_ID,
		"track": WINDOW_ALBUM_ID
	}
	
	DIRECTORY_TITLE_ID = 100
	DIRECTORY_SECONDARY_ID = 200
	DIRECTORY_ITEMS_ID = 300

	PLAY_DIALOG_LIST_ID = 100
	SERIES_LIST_ID = 100
	PHOTO_DIALOG_LIST_ID = 100
	
	HOME_GROUPLIST_ID = 1000
	
	THUMB_WIDTH = 400
	THUMB_HEIGHT = 225
	ART_WIDTH = 1280
	ART_HEIGHT = 720

	MENU_SECTIONS = "SECTION"
	MENU_DIRECT = "DIRECT"
	
	CORE_VIDEO_ATTRIBUTES = ['machineIdentifier','viewGroup','title','key','thumb','art','theme','type','title1','title2','size','index','search','secondary','parentKey','duration','tag','grandparentTheme', 'librarySectionID']
	
	def __init__(self):
		self.plexManager = plex.PlexManager()
		self.config = PlexeeConfig()
		self._windows = dict()

	def getHomeWindow(self):
		id = Plexee.WINDOW_HOME_ID
		if not id in self._windows:
			self._windows[id] = PlexeeHomeWindow(self)
		return self._windows[id]
		
	def getDirectoryWindow(self):
		id = Plexee.WINDOW_DIRECTORY_ID
		if not id in self._windows:
			self._windows[id] = PlexeeDirectoryWindow(self)
		return self._windows[id]

	def getSettingsDialog(self):
		id = Plexee.DIALOG_SETTINGS_ID
		if not id in self._windows:
			self._windows[id] = PlexeeSettingsDialog(self)
		return self._windows[id]
	
	def getConnectionDialog(self):
		id = Plexee.DIALOG_CONNECT_ID
		if not id in self._windows:
			self._windows[id] = PlexeeConnectionDialog(self)
		return self._windows[id]

	def getPlayDialog(self):
		id = Plexee.DIALOG_PLAY_ID
		if not id in self._windows:
			self._windows[id] = PlexeePlayDialog(self)
		return self._windows[id]

	def getWindow(self, id):
		if not id in self._windows:
			if id == Plexee.WINDOW_DIRECTORY_ID:
				self._windows[id] = PlexeeDirectoryWindow(self)
			elif id == Plexee.WINDOW_ALBUM_ID:
				self._windows[id] = PlexeeAlbumWindow(self)
			elif id == Plexee.WINDOW_SEASON_ID:
				self._windows[id] = PlexeeSeasonWindow(self)
			elif id == Plexee.WINDOW_HOME_ID:
				self._windows[id] = PlexeeHomeWindow(self)
			else:	
				return None
		return self._windows[id]
		
	def getWindowID(self, view):
		return Plexee.WINDOW_IDS.get(view, Plexee.WINDOW_DIRECTORY_ID)

	def _myplex(self):
		return self.plexManager.myplex

	def getXmlAttributeList(self, element, subElementName, attributeName, items = 0):
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

	def isEpisode(self, listItem):
		return listItem.GetProperty('type') == 'episode'
		
	def getAdditionalVideoDetails(self, server, listItem):
		"""
		Get the additional media data for a Plex media item
		Used by the Play screen
		"""
		li = mc.ListItem(mc.ListItem.MEDIA_UNKNOWN)
		
		#Copy key attributes
		for a in Plexee.CORE_VIDEO_ATTRIBUTES:
			li.SetProperty(a, listItem.GetProperty(a))
		li.SetPath(listItem.GetPath())

		#Get video detail from plex
		data = mc.Http().Get(listItem.GetPath())
		if not data:
			return listItem
		
		tree = ElementTree.fromstring(data)[0]
		#Set video specific
		generalAttribs = ['title','audioChannels','contentRating','year','summary','viewOffset','rating','tagline']
		episodeAttribs = ['grandparentTitle','index','parentIndex','leafCount','viewedLeafCount']
		for a in (generalAttribs + episodeAttribs):
			if tree.attrib.has_key(a):
				li.SetProperty(a.lower(), util.cleanString(tree.attrib[a]))
	
		#Set episode titles
		if self.isEpisode(li):
			epTitle = util.formatEpisodeTitle(season=li.GetProperty('parentindex'), episode=li.GetProperty('index'), title=li.GetProperty('title'))
			#Set tagline to episode title
			li.SetProperty('tagline',epTitle)
			#set showtitle
			li.SetProperty('title',li.GetProperty('grandparenttitle'))
	
		#Set images
		art = li.GetProperty("art")
		thumb = li.GetProperty("thumb")
		if thumb != "":
			li.SetImage(0, server.getThumbUrl(thumb, 450, 500))
		if art != "":
			url = server.getThumbUrl(art, 980, 580)
			util.logDebug("ART: "+url)
			li.SetImage(1, url)
	
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
		li.SetProperty("genre", util.cleanString(self.getXmlAttributeList(tree, "Genre", "tag", 2)))
		#Director
		li.SetProperty("director", util.cleanString(self.getXmlAttributeList(tree, "Director", "tag")))
		#Writer
		li.SetProperty("writer", util.cleanString(self.getXmlAttributeList(tree, "Writer", "tag")))
		#Actors
		li.SetProperty("actors", util.cleanString(self.getXmlAttributeList(tree, "Role", "tag")))
		
		#Duration
		duration = ""
		if tree.attrib.has_key("duration") and tree.attrib["duration"].isdigit():
			#Format millisecond duration
			duration = util.msToFormattedDuration(int(tree.attrib["duration"]))
		li.SetProperty("durationformatted", duration)

		if tree.attrib.has_key("rating"):
			li.SetProperty("roundedrating", str(int(round(float(tree.attrib["rating"])))))	
	
		return li
		
	def _createListItem(self, server, element, sourceUrl):
		"""
		Create list items from the Plex server and URL to display
		"""
		# Important Properties
		listItem = mc.ListItem(mc.ListItem.MEDIA_UNKNOWN)
		listItem.SetProperty("itemtype", element.tag)
		listItem.SetProperty("machineidentifier", util.cleanString(server.machineIdentifier))
		if element.attrib.has_key("key"):
			listItem.SetPath(server.joinUrl(sourceUrl, element.attrib["key"]))
	
		for attribute in Plexee.CORE_VIDEO_ATTRIBUTES:
			if element.attrib.has_key(attribute):
				#util.logDebug('Property [%s]=[%s]' % (attribute.lower(), util.cleanString(element.attrib[attribute])))
				listItem.SetProperty(attribute.lower(), util.cleanString(element.attrib[attribute]))

		#Special titles
		if self.isEpisode(listItem):
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
			listItem.SetImage(0, server.getThumbUrl(listItem.GetProperty("thumb"), self.THUMB_WIDTH, self.THUMB_HEIGHT))
			
		return listItem

	def _createQueueItems(self):
		"""
		Create Queue items from MyPlex
		"""
		data = self._myplex().getQueueData()
		if not data:
			return mc.ListItems()
		tree = ElementTree.fromstring(data)
		childListItems = mc.ListItems()
		for child in tree:
			listItem = mc.ListItem(mc.ListItem.MEDIA_UNKNOWN)
			listItem.SetProperty("itemtype", "QueueItem")
			listItem.SetPath('1')
			attribs = ['machineidentifier','viewGroup','summary','id','title','key','thumb','type','title1','title2','size','index','search','secondary','parentKey']
			for attribute in attribs:
				if child.attrib.has_key(attribute):
					#util.logDebug('Property [%s]=[%s]' % (attribute.lower(), util.cleanString(element.attrib[attribute])))
					listItem.SetProperty(attribute.lower(), util.cleanString(child.attrib[attribute]))

			# Image paths
			if child.attrib.has_key("thumb"):
				listItem.SetImage(0, listItem.GetProperty("thumb"))
				
			childListItems.append(listItem)

		return childListItems

	def getListItems(self, server, data, sourceUrl, titleListItem = None):
		"""
		Create items to display from a Plex server
		"""
		if not data:
			return None
			
		tree = ElementTree.fromstring(data)
		if not titleListItem:
			titleListItem = self._createListItem(server, tree, sourceUrl)
			
		titleListItem.SetProperty("plexeeview", "grid")
		
		#Set title item art/thumb to display if needed
		titleListItem.SetProperty("art", tree.attrib.get("art",""))
		titleListItem.SetProperty("thumb", tree.attrib.get("thumb",""))
		
		childListItems = mc.ListItems()
		hasChildDirectories = True
		childItems = ["Directory","Photo"]
		#If all directories (with no duration) treat as menu
		for child in tree:
			childListItem = self._createListItem(server, child, sourceUrl)
			childListItems.append(childListItem)
			hasChildDirectories = (hasChildDirectories and childListItem.GetProperty("itemtype") in childItems and childListItem.GetProperty("duration") == "")

		#If collection of directories then this looks like a menu
		if titleListItem.GetProperty("viewgroup") == "secondary":
			titleListItem.SetProperty("ismenu", "1")
		elif hasChildDirectories:
			titleListItem.SetProperty("ismenu", "1")

		titleListItems = mc.ListItems()
		titleListItems.append(titleListItem)

		return WindowInformation(titleListItems, childListItems)

	def getQueueMediaOptions(self, videoItem, mediaIndex = 0):
		"""
		Return list of media and the audio and subtitles for the mediaIndex
		Jinxo: Only the default - and any SRT files are supported at present
		TODO: Simplify for Queue media
		"""
		util.logDebug("Loading media details for external media")
		subtitleItems = mc.ListItems()
		subItem = mc.ListItem(mc.ListItem.MEDIA_UNKNOWN)
		subItem.SetLabel("None")
		subItem.SetPath("")
		subtitleItems.append(subItem)

		audioItems = mc.ListItems()
		mediaItems = mc.ListItems()
		
		data = self._myplex().getQueueData()
		if not data:
			return MediaOptions(mediaItems, subtitleItems, audioItems)
		
		tree = ElementTree.fromstring(data)
		#Match id
		videoNode = False
		for v in tree:
			if v.attrib.get("id") == videoItem.GetProperty("id"):
				videoNode = v
				break
		
		if not videoNode:
			return False
				
		videoItem.SetProperty("videoNode",ElementTree.tostring(videoNode))

		media = videoNode.findall("Media")
		for m in media:
			mediaItem = mc.ListItem(mc.ListItem.MEDIA_UNKNOWN)
			resolution = util.getResolution(m)
			audioCodec = m.attrib.get("audioCodec","")
			width = m.attrib.get("width","")
			height = m.attrib.get("height","")
			if height == "":
				height = m.attrib.get("videoResolution","")
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
					subItem.SetPath(path)
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
		
		return MediaOptions(mediaItems, subtitleItems, audioItems)

	def getMediaOptions(self, server, playItem, mediaIndex = 0):
		"""
		Return list of media and the audio and subtitles for the mediaIndex
		Jinxo: Only the default - and any SRT files are supported at present
		"""
		key = playItem.GetPath()
		util.logDebug("Loading media details for: " + key)
		subtitleItems = mc.ListItems()
		subItem = mc.ListItem(mc.ListItem.MEDIA_UNKNOWN)
		subItem.SetLabel("None")
		subItem.SetPath("")
		subtitleItems.append(subItem)

		audioItems = mc.ListItems()
		mediaItems = mc.ListItems()
		
		data, url = server.getData(key)
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
				if height == "":
					height = m.attrib.get("videoResolution","")
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
						subItem.SetPath(server.getUrl(path))
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
	
	def stopTheme(self):
		if self.config.isPlayingThemeOn():
			self.config.setPlayingThemeOff()
			mc.GetPlayer().Stop()
		
	def playTheme(self, seasonItem):
		if mc.GetPlayer().IsPlaying():
			return
		url = ""
		title = ""
		if type(seasonItem) is not str:
			machineIdentifier = seasonItem.GetProperty("machineidentifier")
			server = self.plexManager.getServer(machineIdentifier)
			if not server:
				return
			
			themeKey = seasonItem.GetProperty("theme")
			if themeKey == "":
				self.stopTheme()
				return
			url = server.getUrl(seasonItem.GetProperty("theme"))
			title = seasonItem.GetProperty("title1")
		else:
			url = seasonItem
			
		li = mc.ListItem(mc.ListItem.MEDIA_AUDIO_MUSIC)
		li.SetPath(url)
		li.SetTitle(title)
		li.SetLabel(title)
		li.SetContentType("audio/mpeg3")
		xbmc.Player(xbmc.PLAYER_CORE_MPLAYER).play(url)
		self.config.setPlayingThemeOn()

	def monitorPlayback(self, server, key, offset, totalTimeSecs, isDirectStream):
		"""
		Update the played progress every 5 seconds while the player is playing
		"""
		progress = 0
		util.logDebug("Monitoring playback to update progress...")
		#Whilst the file is playing back
		player = mc.GetPlayer()
		isWatched = False
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
					server.setMediaWatched(key)
				util.logDebug("-->Updating played duration to "+str(currentTimeSecs*1000))
				server.setMediaPlayedPosition(key, currentTimeSecs*1000)

			#Otherwise, mark as watched
			elif progress >= 95:
				if not isWatched:
					server.setMediaWatched(key)
					isWatched = True
					
			xbmc.sleep(5000)

		#If we get this far, playback has stopped
		util.logDebug("-->Playback Stopped")

	def playQueueItem(self, server, queueItem,  mediaIndex, subtitleIndex, audioIndex, offset=0):
		if offset != 0:
			offset = offset/1000
		
		videoNode = ElementTree.fromstring(queueItem.GetProperty("videoNode"))
		playlist = mc.PlayList(mc.PlayList.PLAYLIST_VIDEO)
		playlist.Clear()

		thumbnailUrl = queueItem.GetProperty("thumb")
		description = util.cleanString(videoNode.attrib.get("summary",""))
		title = util.cleanString(videoNode.attrib.get("title", "Plex Video"))
		contentRating = util.cleanString(videoNode.attrib.get("contentRating",""))
		videoId = videoNode.attrib.get("ratingKey")
		media = videoNode.findall("Media")
		mediaNode = media[mediaIndex]
		
		totalTimeSecs = int(videoNode.attrib.get("duration","0"))
		if totalTimeSecs != 0:
			totalTimeSecs = totalTimeSecs/1000
		
		#Find all media parts to play e.g. CD1, CD2
		partIndex = 0
		for part in mediaNode.findall("Part"):
			partId = part.attrib.get("id")
			li = mc.ListItem(mc.ListItem.MEDIA_VIDEO_CLIP)
			li.SetTitle(title)
			li.SetLabel(title)
			
			#Plex part links to actual part
			data = self._myplex().getQueueLinkData(part.attrib.get("key"))
			if not data:
				util.logError("Unable to retrieve media details to play using url: "+plexLinkToMedia)
				continue
			tree = ElementTree.fromstring(data)
			partNode = tree.find("Video/Media/Part")			
			
			li.SetPath(partNode.attrib.get("key"))
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
			util.logInfo("Added item to play: "+li.GetPath())
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
				subtitleKey = server.getUrl(s.attrib.get("key"))
			
		if subtitleKey == "":
			import os
			noSubPath = os.path.join(mc.GetApp().GetAppMediaDir(), 'media', 'no_subs.srt')
			xbmc.Player().setSubtitles(noSubPath)
		else:
			util.logInfo("Setting subtitles to: " + subtitleKey)
			xbmc.Player().setSubtitles(subtitleKey)

	def playVideoItem(self, server, playItem,  mediaIndex, subtitleIndex, audioIndex, offset=0):
		"""
		Play the video item
		"""
		data, url = server.getData(playItem.GetPath())
		if not data:
			return None
			
		isDirectStream = False
		if offset != 0:
			offset = offset/1000

		tree = ElementTree.fromstring(data)
		videoNode = tree[0]
		playlist = mc.PlayList(mc.PlayList.PLAYLIST_VIDEO)
		playlist.Clear()

		thumbnailUrl = server.getThumbUrl(videoNode.attrib.get("thumb"), 100, 100)
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
			
			#Plex part links to actual part
			if playItem.GetProperty('type') == 'clip':
				plexLinkToMedia = server.getUrl(part.attrib.get("key"))
				data = mc.Http().Get(plexLinkToMedia)
				if not data:
					util.logError("Unable to retrieve media details to play using url: "+plexLinkToMedia)
					continue
				tree = ElementTree.fromstring(data)
				partNode = tree.find("Video/Media/Part")			
				li.SetPath(partNode.attrib.get("key"))
			else:
				if audioIndex != 0:
					util.logDebug("Changing audio stream")
					server.setAudioStream(partId, str(audioIndex))
					server.setSubtitleStream(partId, str(subtitleIndex))
					
					url = server.getDirectStreamUrl(self.plexManager, videoId, mediaIndex, partIndex, offset)
					li.SetPath(url)
					isDirectStream = True
				else:
					li.SetPath(server.getUrl(part.attrib.get("key")))
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
					subtitleKey = server.getUrl(s.attrib.get("key"))
				
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
		#Spawn as seperate thread
		monitorThread = threading.Thread(target=self.monitorPlayback, args=(server, key, offset, totalTimeSecs, isDirectStream))
		monitorThread.start()
		#self.monitorPlayback(server, key, offset, totalTimeSecs, isDirectStream)

	def playMusicItem(self, listItem):
		"""
		Play the music item
		"""
		url = listItem.GetPath()
		machineIdentifier = listItem.GetProperty("machineidentifier")
		server = self.plexManager.getServer(machineIdentifier)

		track = server.getPlexItem(url)
		album = server.getPlexParent(track)
		artist = server.getPlexParent(album)
		if not track:				
			return None
			
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
			li.SetPath(server.getUrl(part.attrib.get('key')))
			playlist.Add(li)
			#util.logInfo("Added item to play: "+li.GetPath())

		playlist.Play(0)

	def getPhotoList(self, listItem):
		"""
		Return a list of all photo items
		"""
		machineIdentifier = listItem.GetProperty("machineidentifier")
		server = self.plexManager.getServer(machineIdentifier)
		data, url = server.getData(listItem.GetProperty('parentKey')+'/children')
		if not data:
			return None

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
				li.SetPath(server.getUrl(key))
				li.SetProperty('rotation','')
				li.SetProperty('zoom','')
				#Resize images
				li.SetImage(0, server.getThumbUrl(part.attrib.get('key'),1280,1280))
				#li.SetImage(0, self.getUrl(part.attrib.get('key')))
				list.append(li)

		return list
		
	def _handleTrackItem(self, listItem):
		self.config.setPlayingThemeOff()
		self.playMusicItem(listItem)

	def activateWindow(self, id):
		util.logDebug("Activate window %s started" % id)
		mc.ActivateWindow(id)
		util.logDebug("Activate window %s ended" % id)
		return mc.GetWindow(id)

	def _handlePhotoItem(self, listItem):
		list = self.getPhotoList(listItem)
		if list != None:
			window = self.activateWindow(Plexee.DIALOG_PHOTO_ID)
			window.GetList(Plexee.PHOTO_DIALOG_LIST_ID).SetItems(list)
			window.GetList(Plexee.PHOTO_DIALOG_LIST_ID).SetFocusedItem(util.getIndex(listItem, list))
		else:
			mc.ShowDialogNotification("Unable to display picture")

	def _handleVideoItem(self, listItem, fromWindowId):
		"""
		Show play screen for video item
		"""
		mc.ShowDialogWait()
		
		machineIdentifier = listItem.GetProperty("machineidentifier")
		server = self.plexManager.getServer(machineIdentifier)
		#Get additional meta data for item to play
		li = self.getAdditionalVideoDetails(server, listItem)
		mediaOptions = self.getMediaOptions(server, li)

		#Show play window
		playDialog = self.getPlayDialog()
		playDialog.activate()
		playDialog.displayPlayItem(li, mediaOptions, fromWindowId)
		mc.HideDialogWait()

	def _handlePlexQueueItem(self, listItem):
		mc.ShowDialogWait()
		#Load media options
		mediaOptions = self.getQueueMediaOptions(listItem)
		if not mediaOptions:
			mc.ShowDialogNotification("Unable to process queue item - has it been changed/removed?")
			return
		#Show play window
		playDialog = self.getPlayDialog()
		playDialog.activate()
		playDialog.displayPlayItem(listItem, mediaOptions)
		mc.HideDialogWait()

	def _handleMenuItem(self, server, clickedItem, windowInformation, fromWindowId):
		"""
		Handles displaying an item that holds child menu items
		"""
		util.logDebug("Handling Menu list")
		mc.ShowDialogWait()
		menuItems = windowInformation.childListItems
		
		if fromWindowId == self.getWindowID('home'):
			#Clicked on Movie etc.. from home menu
			#Grab the menu items - and go to the first one
			url = menuItems[0].GetPath()
			data, url = server.getData(url)
			windowInformation = self.getListItems(server, data, url)
			directoryWindow = self.getDirectoryWindow()
			directoryWindow.activate()
			directoryWindow.updateMenuItems(menuItems)
			directoryWindow.updateContentItems(windowInformation)
		else:
			#Stay in same window, push state
			directoryWindow = self.getWindow(fromWindowId)
			if directoryWindow:
				directoryWindow.activate()
				directoryWindow.updateMenuItems(menuItems)
		mc.HideDialogWait()
		return True

	def _getArtUrl(self, server, listItem):
		art = listItem.GetProperty("art")
		util.logDebug("Art: "+art)
		if art:
			return server.getThumbUrl(art, 980, 580)
		
	def _handleCollectionItem(self, clickedItem, fromWindowId):
		"""
		Handles clicking on a item that is a collection of other items
		"""
		key = clickedItem.GetPath()
		
		# Handle search items
		if clickedItem.GetProperty("search") == "1":
			search = mc.ShowDialogKeyboard(clickedItem.GetProperty("prompt"), "", False)
			if search:
				key += "&query=" + urllib.quote(search)
			else:
				return

		mc.ShowDialogWait()
		try:
			machineIdentifier = clickedItem.GetProperty("machineidentifier")
			server = self.plexManager.getServer(machineIdentifier)

			"""Get the item data and determine the action based on the content"""
			data, url = server.getData(key)
			if clickedItem.GetProperty('title1') == 'Search':
				windowInformation = self.getListItems(server, data, url, clickedItem)
			else:
				windowInformation = self.getListItems(server, data, url)
			if not windowInformation:
				msg = "An unexpected error occurred. Unable to retrieve items."
				util.logDebug(msg)
				mc.ShowDialogNotification(msg)
				return
			titleItem = windowInformation.titleListItems[0]
			isMenuCollection = (titleItem.GetProperty("ismenu") == "1")
			isFromHomeWindow = (fromWindowId == Plexee.WINDOW_HOME_ID)
			
			"""Set the display collection type"""
			displayingCollection = titleItem.GetProperty("viewgroup")
			#Search
			if displayingCollection == "":
				type = clickedItem.GetProperty("type")
				if type == "person":
					displayingCollection = "person_search"
				elif type == "artist":
					displayingCollection = "artist_search"
			#Forces items album, photo, season to be displayed as content
			displayAsContent = ["album","photo","season"]
			if isMenuCollection and displayingCollection not in displayAsContent:
				displayingCollection = "menu"
				
			"""Set the target window"""
			nextWindowID = self.getWindowID(displayingCollection)
			directoryWindow = self.getWindow(nextWindowID)
			window = mc.GetActiveWindow()
			if fromWindowId == nextWindowID and isMenuCollection:
				mc.GetActiveWindow().PushState()
			if nextWindowID != fromWindowId:
				window = self.activateWindow(nextWindowID)

			"""Debug"""
			if self.config.isDebugOn():
				msg = "Displaying Collection: %s, ViewGroup: %s, FromWindowId: %s, NextWindowId: %s" % (displayingCollection, titleItem.GetProperty("viewgroup"), str(fromWindowId), str(nextWindowID))
				util.logDebug(msg)

			if displayingCollection == "menu":
				"""Menu collection"""
				return self._handleMenuItem(server, clickedItem, windowInformation, fromWindowId)
				
			elif displayingCollection == "season":
				"""Displaying TV Show Seasons"""
				if not titleItem.GetImage(0): titleItem.SetImage(0, self._getArtUrl(server, titleItem))
				titleItem.SetImage(1, self._getArtUrl(server, titleItem))
				self.playTheme(windowInformation.titleListItems[0])
			
			elif displayingCollection == "artist_search":
				"""Displaying Artist"""
				if not titleItem.GetImage(0): titleItem.SetImage(0, self._getArtUrl(server, titleItem))
				titleItem.SetImage(1, self._getArtUrl(server, titleItem))
				key = clickedItem.GetProperty('librarysectionid')
				directoryWindow.updateMenu(Plexee.MENU_SECTIONS, server, key)
				titleItem.SetProperty("title2", clickedItem.GetProperty("title"))
			
			elif displayingCollection == "album":
				"""Displaying Album"""
				if not titleItem.GetImage(0): titleItem.SetImage(0, self._getArtUrl(server, titleItem))
				titleItem.SetImage(1, self._getArtUrl(server, titleItem))
			
			elif displayingCollection == "photo":
				"""Displaying a Photo collection"""
				pass
				
			elif displayingCollection == "person_search":
				"""Displaying person search results"""
				#Clear menu
				directoryWindow.updateMenuItems(mc.ListItems())
				titleItem.SetProperty("title2", clickedItem.GetProperty("title"))

			elif displayingCollection == "episode":
				"""Episodes (a Season)"""
				if not titleItem.GetImage(0): titleItem.SetImage(0, self._getArtUrl(server, titleItem))
				titleItem.SetImage(1, self._getArtUrl(server, titleItem))
				if fromWindowId != self.getWindowID("episode"):
					#Set the menu to the list of all seasons
					key = clickedItem.GetProperty('parentkey')+"/children"
					directoryWindow.updateMenu(Plexee.MENU_DIRECT, server, key)
					
			elif displayingCollection == "track":
				"""Tracks (in an Album)"""
				if not titleItem.GetImage(0): titleItem.SetImage(0, self._getArtUrl(server, titleItem))
				titleItem.SetImage(1, self._getArtUrl(server, titleItem))
				if fromWindowId != self.getWindowID("track"):
					#Set the menu to the list of all albums
					key = clickedItem.GetProperty('parentkey')
					if key != "":
						directoryWindow.updateMenu(Plexee.MENU_DIRECT, server, key+"/children")
					else:
						path = clickedItem.GetPath()
						if path.endswith("allLeaves"):
							directoryWindow.updateMenu(Plexee.MENU_DIRECT, server, path.replace("allLeaves","children"))

			else:
				"""All other collections"""
				pass
			
			#Update the new/current window content
			directoryWindow.updateContentItems(windowInformation)
				
		finally:
			mc.HideDialogWait()
		
	def handleItem(self, clickedItem, fromWindowId = 0):
		"""
		Determines the appropriate action for a plex item (a url)
		"""	
		itemType = clickedItem.GetProperty("itemtype")
		type = clickedItem.GetProperty("type")
		util.logDebug("Handling item ItemType: %s, Type: %s, ViewGroup: %s, Path: %s" % (itemType, type, clickedItem.GetProperty("viewgroup"), clickedItem.GetPath()))

		if itemType == "Video":
			#Clicked on a video
			self._handleVideoItem(clickedItem, fromWindowId)
		
		elif itemType == "Track":
			#Clicked on a music track
			self._handleTrackItem(clickedItem)
		
		elif itemType == "Directory" or itemType == "Artist" or itemType == "Album":
			#Clicked on a collection of items
			self._handleCollectionItem(clickedItem, fromWindowId)
			
		elif itemType == "Photo":
			#Clicked on a photo
			self._handlePhotoItem(clickedItem)
			
		elif itemType == "QueueItem":
			#Clicked on a queue item
			self._handlePlexQueueItem(clickedItem)

		# Unknown item
		else:
			mc.ShowDialogNotification("Unknown itemType: %s" % itemType)

	def playVideo(self, server, playItem, mediaIndex, subtitleIndex, audioIndex):
		#util.logDebug("Playing item "+playItem.GetProperty("title"))
		#Check for resume
		viewOffset = playItem.GetProperty("viewOffset")
		if viewOffset == "" or int(viewOffset) == 0:
			viewOffset = 0
		else:
			viewOffset = int(viewOffset)
			f = util.msToResumeTime(viewOffset)
			#show resume dialog
			selection = mc.ShowDialogSelect("Resume", ["Resume from "+f, "Start from beginning"])
			if selection == 1: #from beginning
				viewOffset = 0
			elif selection == 0: #resume
				pass
			else: #cancelled dialog
				return False
		
		#Play item
		itemType = playItem.GetProperty("itemType")
		if itemType == "QueueItem":
			self.playQueueItem(server, playItem, mediaIndex, subtitleIndex, audioIndex, viewOffset)
		else:
			self.playVideoItem(server, playItem, mediaIndex, subtitleIndex, audioIndex, viewOffset)
		return True

	def refresh(self):
		self.loadHome()
		self.initPlexee()
		
	def loadHome(self):
		self.getHomeWindow().activate()

	def initPlexee(self):
		self.plexManager.clearState()
		if not self.config.isAutoConnectOn() and not self.config.isManualConnectOn() and not self.config.isMyPlexConnectOn():
			self.loadContent()
		else:
			mc.ActivateWindow(Plexee.DIALOG_CONNECT_ID)
			
class WindowInformation(object):
	def __init__(self, titleListItems, childListItems):
		self.titleListItems = titleListItems
		self.childListItems = childListItems
		
class MediaOptions(object):
	def __init__(self, mediaItems, subtitleItems, audioItems):
		self.mediaItems = mediaItems
		self.subtitleItems = subtitleItems
		self.audioItems = audioItems
		