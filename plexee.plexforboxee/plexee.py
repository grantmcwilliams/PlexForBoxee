import mc
import os
import sys
import urllib
import util
import uuid
import xbmc
import plex
import time
import random
import threading
from plexgdm import PlexGDM
from elementtree import ElementTree

##
#Provides a simple cache for a windows items to display
#
class PlexeeCache(object):
	def __init__(self, plexee):
		self.dataUrls = []
		self.sectionUrls = []
		self.dataDict = dict()
		self.sectionDict = dict()
		self.size = 15
		self.plexee = plexee
	
	def _getIndex(self, url):
		try:
			isSection = ("/library/sections/" in url)
			if isSection:
				return self.sectionUrls.index(url), isSection
			else:
				return self.dataUrls.index(url), isSection
		except ValueError:
			return -1, isSection
	
	def getItem(self, url, dataHash):
		if not self.plexee.config.isEnableCacheOn():
			return False
		i, isSection = self._getIndex(url)
		if i == -1:
			#Not in cache
			return False
		name = ""
		if isSection:
			name = "section"
			dict = self.sectionDict
		else:
			name = "data"
			dict = self.dataDict

		item = dict[url]
		if item.dataHash != dataHash:
			return False
		util.logDebug("Retrieved from %s cache: %s" % (name,url))
		return item
			
	def addItem(self, url, windowInformation):
		if not self.plexee.config.isEnableCacheOn():
			return
		i, isSection = self._getIndex(url)
		if isSection:
			urls = self.sectionUrls
			dict = self.sectionDict
			name = "section"
		else:
			urls = self.dataUrls
			dict = self.dataDict
			name = "data"
			
		if i == -1:
			#Add to cache
			size = len(urls)
			if size >= self.size:
				urlToRemove = urls[0]
				del urls[0]
				del dict[urlToRemove]
				util.logDebug("Removing from %s cache: %s" % (name,urlToRemove))
			urls.append(url)
			dict[url] = windowInformation
			util.logDebug("Added to %s cache (size=%i): %s" % (name, size, url))
		else:
			#Update cache
			dict[url] = windowInformation
			util.logDebug("Updated %s cache (size=%i): %s" % (name, i, url))

##
#Represents a Boxee window.
#			
class PlexeeWindow(object):
	def __init__(self, plexee):
		self.plexee = plexee
		self.initialised = False
		self.window = None
	
	def load(self):
		util.logDebug("On load %s started" % self.getId())
		try:
			self.onLoad()
			util.logDebug("On load %s ended" % self.getId())
		except:
			util.logError("Unexpected error whole loading: %s" % sys.exc_info()[0])			

	def unload(self):
		util.logDebug("On unload %s started" % self.getId())
		try:
			self.onUnload()
			util.logDebug("On unload %s ended" % self.getId())
		except:
			util.logError("Unexpected error while unloading: %s" % sys.exc_info()[0])			

	def activate(self):
		try:
			self.plexee.player.stopWaiting()
			id = self.getId()
			util.logDebug("Activate Window %s started" % id)
			mc.ActivateWindow(id)
			#Initialise links to controls
			self.window = mc.GetWindow(self.getId())
			self.init()
			#Do any actions on activation of window
			self.onActivate()
			util.logDebug("Activate Window %s ended" % id)
		except:
			util.logError("Unexpected error while activating: %s" % sys.exc_info()[0])

	def onActivate(self): pass
	def onLoad(self): pass
	def onUnload(self): pass
	def doInit(self): pass
	def init(self):
		if not self.initialised:
			self.doInit()
			self.initialised = True

	def handleItem(self, clickedItem):
		"""
		Determines the appropriate action for a plex item (a url)
		"""	
		itemType = clickedItem.GetProperty("itemtype")
		type = clickedItem.GetProperty("type")
		util.logDebug("Handling item ItemType: %s, Type: %s, ViewGroup: %s, Path: %s" % (itemType, type, clickedItem.GetProperty("viewgroup"), clickedItem.GetPath()))
		
		mc.ShowDialogWait()
		try:

			if itemType == "Video":
				#Clicked on a video
				self.plexee._handleVideoItem(clickedItem, self.getId())
			
			elif itemType == "Track":
				#Clicked on a music track
				self.plexee._handleTrackItem(clickedItem)
			
			elif itemType == "Directory" or itemType == "Artist" or itemType == "Album":
				#Clicked on a collection of items
				self.plexee._handleCollectionItem(clickedItem, self.getId())
				
			elif itemType == "Photo":
				#Clicked on a photo
				self.plexee._handlePhotoItem(clickedItem)
				
			elif itemType == "QueueItem":
				#Clicked on a queue item
				self.plexee._handlePlexQueueItem(clickedItem)

			# Unknown item
			else:
				mc.ShowDialogNotification("Unknown itemType: %s" % itemType)
		
		finally:
			mc.HideDialogWait()

##
#Represents a Boxee dialog window - extends PlexeeWindow
#			
class PlexeeDialog(PlexeeWindow):
	def close(self): xbmc.executebuiltin("Dialog.Close("+str(self.getId())+")")
	def __init__(self, plexee):	PlexeeWindow.__init__(self, plexee)

##
#The dialog object for the for Photo Dialog screen
#
class PlexeePhotoDialog(PlexeeDialog):
	def getId(self): return Plexee.DIALOG_PHOTO_ID

	def doInit(self):
		window = self.window
		self.photoList = window.GetList(100)
		self.loadingLabel = window.GetLabel(101)
		self.menuPanel = window.GetControl(300)
		self.rotateButton = window.GetButton(110)
		self.slideshow = window.GetControl(102)
		self.slideOptions = [1,2,3]
		self.slideThread = threading.Thread(target=self.threadShow)

	def rotate(self, clockwise=True):
		#increment from 8 to 5 rotates clockwise
		li = self.getFocusedPhoto()
		rotation = li.GetProperty('rotation')
		if rotation.isdigit():
			r = int(rotation)
		else:
			if clockwise: r=9
			else: r=0
		if clockwise:
			if r<5:
				r=r+4
			else:
				r = r - 1
			if r<5:
				r=8
		else:
			if r>4:
				r=r-4
			else:
				r = r + 1
			if r>4:
				r=1
		li.SetProperty('rotation',str(r))
		
	def zoom(self):
		li = self.getFocusedPhoto()
		zoom = li.GetProperty('zoom')
		if zoom == "":
			z = 1
		else:
			z = int(zoom) + 1
		if z>5:
			z=0
		li.SetProperty('zoom',str(z))

	def toggleMenu(self, on):
		if not on:
			self.menuPanel.SetVisible(False)
			self.rotateButton.SetFocus()
		else:
			self.stopSlideshow()
			self.menuPanel.SetVisible(True)
			self.menuPanel.SetFocus()

	def showSettings(self):
		settingsDialog = self.plexee.getSettingsDialog()
		settingsDialog.activate()
		settingsDialog.showPhotoSettings()

	def getFocusedPhoto(self):
		return self.photoList.GetItem(self.photoList.GetFocusedItem())
		
	def showNextImage(self, forward=True):
		list = self.photoList
		li = self.getFocusedPhoto()
		li.SetProperty('rotation','')
		li.SetProperty('zoom','')
		listSize = len(list.GetItems())
		if listSize == 0:
			return
		
		if forward:
			index = list.GetFocusedItem() + 1
			if index >= listSize:
				index = 0
		else:
			index = list.GetFocusedItem() - 1
			if index < 0:
				index = listSize - 1
		
		#loading.SetVisible(False)
		list.SetFocusedItem(index)
		#xbmc.sleep(500)
		#loading.SetVisible(True)

	def stopSlideshow(self):
		if self.slideshow.IsVisible():
			self.slideshow.SetVisible(False)
			try:
				self.slideThread.join()
			except: pass

	def threadShow(self):
		config = self.plexee.config
		list = self.photoList
		if config.isSlideshowZoomOn():
			slideShowDelay = 5
		else:
			slideShowDelay = config.getSlideShowDelaySec()
		
		pos = list.GetFocusedItem()
		while self.slideshow.IsVisible():
			i=0
			while i<slideShowDelay*1000:
				if not self.slideshow.IsVisible():
					break
				i = i + 100
				xbmc.sleep(100)
			self.showNextImage()
				
		#Slideshow finished
		for li in list.GetItems():
			li.SetProperty('slideshow','')
		list.SetFocusedItem(pos)
		
		
	def startSlideshow(self):
		list = self.photoList
		#set slideshow options
		opt = 0
		for li in list.GetItems():
			li.SetProperty('slideshow', str(self.slideOptions[opt]))
			opt = opt + 1
			if opt>len(self.slideOptions)-1:
				opt = 0

		#show slides until stopped
		self.slideshow.SetVisible(True)
		self.toggleMenu(on=False)
		self.slideThread.start()
	
##
#The window object for the for Directory screen
#
class PlexeeDirectoryWindow(PlexeeWindow):

	MUSIC_GROUP = 599
	HOME_BUTTON = 50
	MENU_LIST = 200
	CONTENT_LIST = 300
	
	def getMenuItems(self):
		return self.window.GetList(Plexee.DIRECTORY_SECONDARY_ID).GetItems()
	
	def hide(self):
		self.window.GetList(100).SetVisible(False)
		self.window.GetList(200).SetVisible(False)
		self.window.GetList(300).SetVisible(False)
	
	def show(self):
		self.window.GetList(100).SetVisible(True)
		self.window.GetList(200).SetVisible(True)
		self.window.GetList(300).SetVisible(True)

	def getId(self): return Plexee.WINDOW_DIRECTORY_ID
	def __init__(self, plexee):
		self.clickedItem = None
		self.server = None
		PlexeeWindow.__init__(self, plexee)

	def onMenuUpdated(self): pass
	def onContentUpdated(self): pass
	
	def menuClicked(self):
		clickedItem = mc.GetFocusedItem(self.getId(), PlexeeDirectoryWindow.MENU_LIST)
		self.handleMenuItem(clickedItem)	
	
	def contentClicked(self):
		clickedItem = mc.GetFocusedItem(self.getId(), PlexeeDirectoryWindow.CONTENT_LIST)
		self.handleItem(clickedItem)
	
	def handleMenuItem(self, clickedItem):
		"""
		Handles clicking on a menu item and displays a submenu or updates the displsyed content
		"""
		server = self.server
		if not server:
			server = self.plexee.getItemServer(clickedItem)
			
		config = self.plexee.config
		key = clickedItem.GetPath()
		
		#Show search dialog if search menu item clicked
		if clickedItem.GetProperty("search") == "1":
			search = mc.ShowDialogKeyboard(clickedItem.GetProperty("prompt"), "", False)
			if search:
				key += "&query=" + urllib.quote(search)
			else:
				return
		mc.ShowDialogWait()
		try:
			"""Get the item data and determine the action based on the content"""
			data, url = server.getData(key)
			if clickedItem.GetProperty('title1') == 'Search':
				windowInformation = self.plexee.getListItems(server, data, url, clickedItem)
			else:
				windowInformation = self.plexee.getListItems(server, data, url)
			if not windowInformation:
				msg = "An unexpected error occurred. Unable to retrieve items."
				util.logDebug(msg)
				mc.ShowDialogNotification(msg)
				return
			titleItem = windowInformation.titleListItem
			isMenuCollection = (titleItem.GetProperty("ismenu") == "1")
			
			"""Set the display collection type"""
			displayingCollection = self.plexee.getDisplayingCollection(clickedItem, titleItem)
				
			"""Debug"""
			msg = "Handling menu item - displaying: %s, ViewGroup: %s, InWindowId: %s" % (displayingCollection, titleItem.GetProperty("viewgroup"), str(self.getId()))
			util.logDebug(msg)

			if isMenuCollection and displayingCollection not in Plexee.DISPLAY_AS_CONTENT:
				self.pushState()
				menuItems = windowInformation.childListItems
				self.updateMenuItems(menuItems)
			else:
				# if displayingCollection == "track" and self.getId() != Plexee.WINDOW_ALBUM_ID:
					# if not titleItem.GetImage(0): titleItem.SetImage(0, self.plexee._getArtUrl(server, titleItem))
					# titleItem.SetImage(1, self.plexee._getArtUrl(server, titleItem))
					# albumWindow = self.plexee.getAlbumWindow()
					# menuItems = self.getMenuItems()
					# albumWindow.activate(clickedItem, server)
					# albumWindow.updateMenuItems(menuItems)
					# albumWindow.updateContentItems(windowInformation)
				# else:
				if displayingCollection in ["track","episode"]:
					if not titleItem.GetImage(0): titleItem.SetImage(0, self.plexee._getArtUrl(server, titleItem))
					titleItem.SetImage(1, self.plexee._getArtUrl(server, titleItem))
				self.updateContentItems(windowInformation)
		finally:
			mc.HideDialogWait()
	
	def moveUpFromContent(self):
		window = self.window
		if window.GetControl(self.MUSIC_GROUP).IsVisible():
			window.GetControl(self.MUSIC_GROUP).SetFocus()
		else:
			window.GetControl(self.HOME_BUTTON).SetFocus()	
	
	def activate(self, clickedItem, server):
		self.clickedItem = clickedItem
		self.server = server
		PlexeeWindow.activate(self)

	def setTitleItem(self, item):
		self.window.GetList(Plexee.DIRECTORY_TITLE_ID).SetItems(item)
		
	def pushState(self):
		mc.GetActiveWindow().PushState()
		
	def updateMenuItems(self, menuItems):
		self.window.GetList(Plexee.DIRECTORY_SECONDARY_ID).SetItems(menuItems)
		self.onMenuUpdated()

	def updateContentItems(self, windowInformation):
		window = self.window
		titleItems = window.GetList(Plexee.DIRECTORY_TITLE_ID).GetItems()
		currentHash = ""
		if len(titleItems) == 1:
			currentHash = titleItems[0].GetProperty('hash')
		newHash = windowInformation.titleListItem.GetProperty('hash')
		if currentHash == newHash:
			util.logDebug("Skipping update content hasn't changed")
			self.show()
			return
		t = mc.ListItems()
		t.append(windowInformation.titleListItem)
		self.setTitleItem(t)
		window.GetList(Plexee.DIRECTORY_ITEMS_ID).SetItems(windowInformation.childListItems)
		self.show()
		window.GetControl(Plexee.DIRECTORY_ITEMS_ID).SetFocus()
		self.onContentUpdated()
		
	def getContentList(self): return self.window.GetList(Plexee.DIRECTORY_ITEMS_ID)
	def getMenuList(self): return self.window.GetList(Plexee.DIRECTORY_SECONDARY_ID)
	def getSelectedMenuItem(self): return mc.GetFocusedItem(self.getId(), PlexeeDirectoryWindow.MENU_LIST)
	def getSelectedContentItem(self): return mc.GetFocusedItem(self.getId(), PlexeeDirectoryWindow.CONTENT_LIST)
		
	def homeClicked(self):
		mc.ShowDialogWait()
		try:
			self.plexee.player.stopTheme()
			self.plexee.clearWindowState()
			self.plexee.getHomeWindow().activate()
		finally:
			mc.HideDialogWait()
		
##
#The window object for the for Directory Album screen
#
class PlexeeAlbumWindow(PlexeeDirectoryWindow):
	def getId(self): return Plexee.WINDOW_ALBUM_ID
	def __init__(self, plexee):	PlexeeDirectoryWindow.__init__(self, plexee)
		
##
#The window object for the for Directory Album screen
#
class PlexeePlaylistWindow(PlexeeDirectoryWindow):
	def getId(self): return Plexee.WINDOW_PLAYLIST_ID
	def __init__(self, plexee):
		PlexeeDirectoryWindow.__init__(self, plexee)
		self.currentMenuItem = self._getCurrentMenuItem()
	
	def activate(self):
		PlexeeWindow.activate(self)
	
	def _getCurrentMenuItem(self):
		t = mc.ListItem()
		t.SetTitle("<Current Playlist>")
		t.SetProperty("title",t.GetTitle())
		t.SetProperty("playlisttype","audio")
		return t
	
	def onActivate(self):
		#Have playlists changed?
		hash, menuItems = self.getMyPlaylistItems()
		pos = self.getMenuList().GetFocusedItem()
			
		t = mc.ListItems()
		t.append(self.currentMenuItem)
		for m in menuItems: t.append(m)
		if pos != 0 and self.menuHash == hash:
			return
		self.menuHash = hash
		self.updateMenuItems(t)
		self.menuClicked()
	
	def doInit(self):
		self.menuHash = ""
		t = mc.ListItem(mc.ListItem.MEDIA_UNKNOWN)
		t.SetProperty('title1','Playlists')
		t.SetProperty('title2','Click a track/video to play the list')
		self.titleItem = t
		l = mc.ListItems()
		l.append(t)
		self.window.GetList(Plexee.DIRECTORY_TITLE_ID).SetItems(l)
		xbmc.executebuiltin("PlayerControl(RepeatOff)")
	
	def getMyPlaylistItems(self):
		libraryListItems = mc.ListItems()
		myServers = self.plexee.plexManager.myServers
		hash = ""
		for machineID in myServers:
			server = myServers[machineID]
			data, url = server.getPlaylistData()
			windowInformation = self.plexee.getListItems(server, data, url, None)
			hash = hash + windowInformation.dataHash
			for childListItem in windowInformation.childListItems:
				childListItem.SetTitle(childListItem.GetProperty("title"))
				libraryListItems.append(childListItem)
		return hash, libraryListItems

	def setTitleItem(self, item):
		pass
	
	def repeatList(self):
		if not self.window.GetToggleButton(805).IsSelected():
			xbmc.executebuiltin("PlayerControl(RepeatOff)")
		else:
			xbmc.executebuiltin("PlayerControl(RepeatAll)")
	
	def shuffleList(self):
		items = self.getContentList().GetItems()
		l = []
		for i in items: l.append(i)
		random.shuffle(l)
		m = mc.ListItems()
		for i in l: m.append(i)
		self.getContentList().SetItems(m)
	
	def deleteList(self, menuItem = None, internal = False):
		player = self.plexee.player
		if not menuItem:
			menuItem = self.getSelectedMenuItem()
		key = menuItem.GetProperty('ratingkey')
		server = self.plexee.getItemServer(menuItem)
		title = util.cleanString(menuItem.GetTitle())
		if not internal:
			selection = mc.ShowDialogConfirm("Delete?", "Are you sure you wish to delete the playlist ["+title+"]?", "No", "Yes")
			if not selection:
				return
		if menuItem.GetTitle() == self.currentMenuItem.GetTitle():
			player.getMusicPlaylist().Clear()
			self.menuClicked()
			return
		if key != "" and server:
			self.plexee.plexManager.deletePlaylist(server, key)
			if not internal:
				self.onActivate()
				self.getMenuList().SetFocus()
	
	def playList(self):
		contentList = self.getContentList()
		startIndex = contentList.GetFocusedItem()
		menuItem = self.getSelectedMenuItem()
		server = self.plexee.getItemServer(menuItem)
		player = self.plexee.player

		if menuItem.GetTitle() == self.currentMenuItem.GetTitle():
			#Boxee current playlist
			player.clearMusicList()
			t = mc.ListItems()
			for i in contentList.GetItems():
				player.addMusic(i)
			player.playMusicList(startIndex)
			return
		
		type = menuItem.GetProperty('playlisttype')
		util.logDebug("Playlist Type: "+type)
		items = mc.ListItems()
		if type == 'audio':
			for item in contentList.GetItems():
				self.plexee.createAndAddMusicItem(items, item)
			player.playMusicItems(items, startIndex)
		else:
			player.clearVideoList()
			for item in contentList.GetItems():
				self.plexee.queueVideoItem(server, item)
			player.playVideoList(startIndex)
	
	def stop(self):
		mc.GetPlayer().Stop()

	def pause(self):
		player = self.plexee.player
		if not mc.GetPlayer().IsPlayingAudio():
			self.playList()
		else:
			player.pause()
	
	def contentOnRight(self):
		index = self.getContentList().GetFocusedItem()
		self.getInfoGroup().SetFocus()
	
	def infoOnLeft(self):
		self.getContentList().SetFocus()
	
	def deleteClicked(self):
		player = self.plexee.player
		selection = mc.ShowDialogConfirm("Delete?", "Are you sure you wish to delete this item from the playlist?", "No", "Yes")
		if not selection:
			return
		clickedItem = self.getSelectedContentItem()
		menuItem = self.getSelectedMenuItem()
		playlistId = menuItem.GetProperty('ratingkey')
		server = self.plexee.getItemServer(clickedItem)
		itemId = clickedItem.GetProperty("playlistitemid")
		if itemId != "":
			self.plexee.plexManager.deleteFromPlaylist(server, playlistId, itemId)
		else:
			#Delete from playlist queue
			removeIndex = self.getContentList().GetFocusedItem()
			menuItem = self.getSelectedMenuItem()
			type = menuItem.GetProperty('playlisttype')
			if type == 'audio':
				player.removeMusicItem(self.getContentList(), removeIndex)
			else:
				player.removeVideoItem(self.getContentList(), removeIndex)
		self.menuClicked()
	
	def selectMenuItem(self, name):
		menuItems = self.getMenuList()
		i = 0
		found = False
		for m in menuItems.GetItems():
			if m.GetTitle() == name:
				menuItems.SetFocusedItem(i)
				found = True
			i = i + 1
		if found:
			self.menuClicked()
	
	def menuClicked(self):
		player = self.plexee.player
		clickedItem = self.getSelectedMenuItem()
		type = clickedItem.GetProperty('playlisttype')
		server = self.plexee.getItemServer(clickedItem)
		if clickedItem.GetTitle() == self.currentMenuItem.GetTitle():
			util.logDebug("Show playlist..." + type)
			if type == 'audio':
				childItems = player.getDisplayMusicList()
			else:
				childItems = player.getDisplayVideoList()
			self.getContentList().SetItems(childItems)
			size = len(childItems)
		else:
			self.handleMenuItem(clickedItem)
			childItems = self.getContentList().GetItems()
			size = len(childItems)
			self.titleItem.SetProperty('size',str(size))
		if size > 0:
			tempList = range(size)
			random.shuffle(tempList)
			pos = tempList[0]
			url = False
			if not server:
				#Current Playlist
				if type == 'audio':
					item = player.getCurrentMusicListItem()
				else:
					item = player.getCurrentVideoListItem()
				if not item:
					item = self.getContentList().GetItems()[0]
				server = self.plexee.getItemServer(item)
				if server:
					url = self.plexee._getArtUrl(server, item)
			else:
				url = self.plexee._getArtUrl(server, childItems[pos])
			if url:
				self.titleItem.SetImage(0, url)
				l = mc.ListItems()
				l.append(self.titleItem)
				self.window.GetList(Plexee.DIRECTORY_TITLE_ID).SetItems(l)

	def contentClicked(self):
		mc.ShowDialogWait()
		try:
			self.playList()
		finally:
			mc.HideDialogWait()
		
	def saveList(self):
		menuItem = self.getSelectedMenuItem()
		name = ""
		if menuItem.GetTitle() != self.currentMenuItem.GetTitle():
			selection = mc.ShowDialogSelect("New or Update?", ["Save as a new playlist?","Update the current playlist?","Cancel"])
			if selection == 1:
				name = menuItem.GetTitle()
				self.deleteList(menuItem, internal = True)
			elif selection == 0:
				pass	
			else:
				return
		if name == "":
			name = mc.ShowDialogKeyboard("Enter Playlist name", "", False)
		if name == "":
			return
		items = self.getContentList().GetItems()
		if len(items) == 0:
			return
		item = items[0]
		server = self.plexee.getItemServer(item)
		if not server:
			mc.ShowDialogNotification("Failed to determine Plex server to save list to")
		else:
			self.plexee.plexManager.savePlaylist(server, name, util.getProperties(self.getContentList().GetItems(),["key"]))
			self.onActivate()
			self.selectMenuItem(name)
				
##
#The window object for the for Home screen
#
class PlexeeHomeWindow(PlexeeWindow):
	
	MUSIC_GROUP = 599
	SETTINGS_BUTTON = 30

	def getId(self): return Plexee.WINDOW_HOME_ID

	def __init__(self, plexee):
		PlexeeWindow.__init__(self, plexee)
	
	def onUnload(self): pass
	
	def refresh(self):
		self.loadContent()
	
	def itemClicked(self, listId):
		clickedItem = mc.GetFocusedItem(self.getId(), listId)
		self.handleItem(clickedItem)

	def moveUpFromContent(self):
		window = self.window
		if window.GetControl(self.MUSIC_GROUP).IsVisible():
			window.GetControl(self.MUSIC_GROUP).SetFocus()
		else:
			window.GetControl(self.SETTINGS_BUTTON).SetFocus()	

	def doInit(self):
		window = self.window
		self.myLibrary = window.GetList(110)
		self.sharedLibraries = window.GetList(210)
		self.myChannels = window.GetList(310)
		self.myRecentlyAdded = window.GetList(410)
		self.myOnDeck = window.GetList(510)
		self.searchList = window.GetList(710)
		self.myQueueList = window.GetList(810)
		self.homeGroupList = window.GetControl(Plexee.HOME_GROUPLIST_ID)
	
	def userClicked(self):
		#change user
		self.plexee.getUserDialog().activate()

	def playlistClicked(self):
		self.plexee.getPlaylistWindow().activate()
	
	def searchClicked(self):
		mc.ShowDialogWait()
		try:
			config = self.plexee.config
			#searchText = mc.ShowDialogKeyboard("Search for?", config.getLastSearch(), False)
			searchText = mc.ShowDialogKeyboard("Search for?", "", False)
			if searchText != "":
				config.setLastSearch(searchText)
				self.searchList.SetItems(self.getSearchItems(searchText))
			else:
				config.setLastSearch('')
				blankItems = mc.ListItems()
				self.searchList.SetItems(blankItems)
		finally:
			mc.HideDialogWait()	
	
	def refreshMyOnDeck(self):
		try:
			self.myOnDeck.SetItems(self.getMyOnDeckItems())
		except:
			pass
	
	def onLoad(self):
		self.plexee.player.stopTheme()
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
			if windowInformation is None: continue
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
			if windowInformation is None: continue
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
			if windowInformation is None: continue
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
			if windowInformation is None: continue
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
			if windowInformation is None: continue
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
			if windowInformation is None: continue
			for childListItem in windowInformation.childListItems:
				#Only allow known types
				if childListItem.GetProperty('itemtype') == 'Video' or childListItem.GetProperty('itemtype') == 'Track' or childListItem.GetProperty('itemtype') == 'Directory':
					childListItem.SetProperty('title1', 'Search')
					libraryListItems.append(childListItem)
		return libraryListItems
	
class PlexeePlayDialog(PlexeeDialog):
	"""
	The dialog object for the for Play Dialog screen
	"""

	def getId(self):
		return Plexee.DIALOG_PLAY_ID

	def __init__(self, plexee):
		PlexeeDialog.__init__(self, plexee)
		self.refreshOnDeck = False
	
	def doInit(self):
		window = self.window
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
		self.server = self.plexee.getItemServer(self.playItem)
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
			self.plexee.player.playTheme(item)

	def onLoad(self):
		pass
		
	def onUnload(self):
		self.plexee.player.stopTheme()
	
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

##
#The dialog object for the for Connection Dialog screen
#
class PlexeeConnectionDialog(PlexeeDialog):

	def getId(self): return Plexee.DIALOG_CONNECT_ID
	
	def __init__(self, plexee): PlexeeDialog.__init__(self, plexee)
	
	def doInit(self):
		window = self.window
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
			
			#Set user
			localUser = config.getLocalUser()
			if localUser != "":
				localUsers = plexManager.getLocalUsers()
				if len(localUsers) > 1:
					for l in localUsers:
						if l['id'] == localUser:
							plexManager.switchUser(l['token'],l['machineidentifier'])
			
			self.plexee.getHomeWindow().loadContent()
		finally:
			mc.HideDialogWait()

##
#The dialog object for the for User Dialog screen
#
class PlexeeUserDialog(PlexeeDialog):

	def getId(self): return Plexee.DIALOG_USER_ID
	
	def __init__(self, plexee): PlexeeDialog.__init__(self, plexee)
	
	def doInit(self):
		window = self.window
		self.contentList = window.GetList(300)
		self.message = window.GetLabel(200)
		self.initialised = True

	def onLoad(self):
		self.message.SetVisible(True)
		users = self.plexee.plexManager.getLocalUsers()
		if len(users) == 1:
			self.message.SetLabel("There is no user to switch to! (You can set these up on you Plex Server)")
			return
		else:
			self.message.SetVisible(False)
		
		listItems = mc.ListItems()
		
		for user in users:
			util.logDebug("Adding user: %s" % user['name'])
			li = mc.ListItem(mc.ListItem.MEDIA_UNKNOWN)
			li.SetProperty("itemtype", "UserItem")
			li.SetPath('1')
			attribs = ['id','token','thumb','name','machineidentifier']
			for attribute in attribs:
				if user.has_key(attribute):
					li.SetProperty(attribute.lower(), user[attribute])
			li.SetImage(0, user['thumb'])
			listItems.append(li)
			
		self.contentList.SetItems(listItems)
		
	def onUnload(self):
		pass

	def userClicked(self):
		clickedItem = mc.GetFocusedItem(self.getId(), 300)
		util.logDebug("Name: %s" % clickedItem.GetProperty('name'))
		machineID = clickedItem.GetProperty("machineidentifier")
		self.plexee.plexManager.switchUser(clickedItem.GetProperty("token"), machineID)
		
		#TODO: change to a field that indicates prime user
		if machineID != '0':
			self.plexee.config.setLocalUser(clickedItem.GetProperty("id"))
		else:
			self.plexee.config.setLocalUser("")
		
		self.close()
		self.plexee.getHomeWindow().refresh()

##
#The dialog object for the for Settings Dialog screen
#
class PlexeeSettingsDialog(PlexeeDialog):

	def getId(self): return Plexee.DIALOG_SETTINGS_ID
	
	def __init__(self, plexee): PlexeeDialog.__init__(self, plexee)
	
	# def _showNotification(self, msg):
		# dlg = self.window.GetControl(98)
		# lbl = self.window.GetLabel(99)
		# lbl.SetLabel(msg)
		# dlg.SetVisible(True)
		# xbmc.sleep(2000)
		# dlg.SetVisible(False)
		
	# def showNotification(self, msg):
		# t = threading.Thread(target=self._showNotification, args=(msg))
		# t.start()
	
	def doInit(self):
		window = self.window
		#Connect Settings
		self.discoverClients = window.GetToggleButton(100)
		self.discoverClientTime = window.GetEdit(101)
		self.manualClient = window.GetToggleButton(102)
		self.manualClientHost = window.GetEdit(103)
		self.manualClientPort = window.GetEdit(104)
		self.myPlex = window.GetToggleButton(105)
		self.myPlexUsername = window.GetEdit(106)
		self.myPlexPassword = window.GetEdit(107)
		#Photo Settings
		self.photoSettingsButton = window.GetButton(43)
		self.slideShowZoom = window.GetToggleButton(300)
		self.slideShowDelay = window.GetEdit(301)
		#Experience Settings
		self.playThemes = window.GetToggleButton(200)
		self.queueAudio = window.GetToggleButton(201)
		#Advanced Settings
		self.advancedSettingsButton = window.GetButton(49)
		self.debugToggle = window.GetToggleButton(900)
		self.cacheToggle = window.GetToggleButton(901)

	def onLoad(self):
		self.connectOnClose = False
		self.loadConnectSettings()
		self.loadPhotoSettings()
		self.loadExperienceSettings()
		self.loadAdvancedSettings()
		
	def onUnload(self):
		pass
	
	def loadAdvancedSettings(self):
		config = self.plexee.config
		self.cacheToggle.SetSelected(config.isEnableCacheOn())
		self.debugToggle.SetSelected(config.isDebugOn())
	
	def showAdvancedSettings(self):
		self.advancedSettingsButton.SetFocus()
	
	def saveAdvancedSettings(self):
		config = self.plexee.config
		if self.cacheToggle.IsSelected():
			config.setEnableCacheOn()
		else:
			config.setEnableCacheOff()
		if self.debugToggle.IsSelected():
			config.setDebugOn()
		else:
			config.setDebugOff()
		mc.ShowDialogNotification("Saved")

	def loadExperienceSettings(self):
		config = self.plexee.config
		self.playThemes.SetSelected(config.isPlayThemesOn())
		self.queueAudio.SetSelected(config.isQueueAudioOn())
	
	def showExperienceSettings(self):
		self.experienceSettingsButton.SetFocus()
	
	def saveExperienceSettings(self):
		config = self.plexee.config
		if self.playThemes.IsSelected():
			config.setPlayThemesOn()
		else:
			config.setPlayThemesOff()
		if self.queueAudio.IsSelected():
			config.setQueueAudioOn()
		else:
			config.setQueueAudioOff()
		mc.ShowDialogNotification("Saved")

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
		mc.ShowDialogNotification("Saved")

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
		mc.ShowDialogNotification("Saved")

##
#The dialog object for the for Settings Dialog screen
#
class PlexeeConfig(object):
	def __init__(self):
		self.config = mc.GetApp().GetLocalConfig()
	def _isFlagSet(self, name, default=False):
		val = self.config.GetValue(name)
		if val == "" and default:
				val = "1"
		return (val == "1")
	def _setFlag(self, name, bool):
		if bool:
			self.config.SetValue(name,"1")
		else:
			self.config.SetValue(name,"0")
		
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
	
	""" Internal state values """
	def hasStarted(self): return self._isFlagSet("started")
	def setHasStarted(self, bool): self._setFlag("started", bool)
	def isPlayingThemeOn(self): return self._isFlagSet("playingtheme")
	def setPlayingThemeOn(self): self._setFlag("playingtheme", True)
	def setPlayingThemeOff(self): self._setFlag("playingtheme", False)
	
	def getLocalUser(self) : return self.config.GetValue("localuser");
	def setLocalUser(self, val) : self.config.SetValue("localuser", val);

	""" Connection Settings """
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
	def getDiscoveryTime(self): return self._getInt("discovertime",1)
	def setDiscoveryTime(self, val): return self._setInt("discovertime",val,"Discovery Time",1,5)
	def getMyPlexUser(self): return self.config.GetValue("myplexusername")
	def setMyPlexUser(self, val): self.config.SetValue("myplexusername",val)
	def getMyPlexPassword(self): return self.config.GetValue("myplexpassword")
	def setMyPlexPassword(self, val): self.config.SetValue("myplexpassword",val)
	def getLastSearch(self): return self.config.GetValue("lastsearch")
	def setLastSearch(self, val): self.config.SetValue("lastsearch",val)

	"""Experience Settings"""
	def isPlayThemesOn(self): return self._isFlagSet("playthemes", True)
	def setPlayThemesOn(self):	self._setFlag("playthemes", True)
	def setPlayThemesOff(self):	self._setFlag("playthemes", False)
	def isQueueAudioOn(self): return self._isFlagSet("queueaudio", True)
	def setQueueAudioOn(self):	self._setFlag("queueaudio", True)
	def setQueueAudioOff(self):	self._setFlag("queueaudio", False)

	"""Photo Settings"""
	def isSlideshowZoomOn(self): return self._isFlagSet("slideshowzoom")
	def setSlideshowZoomOn(self):	self._setFlag("slideshowzoom", True)
	def setSlideshowZoomOff(self):	self._setFlag("slideshowzoom", False)
	def getSlideShowDelaySec(self): return self._getInt("slideshowdelay",5)
	def setSlideShowDelaySec(self, val): return self._setInt("slideshowdelay",val,"SlideShow Delay",1,120)
	
	"""Advanced Settings"""
	def isDebugOn(self): return self._isFlagSet("debug")
	def setDebugOn(self):	self._setFlag("debug", True)
	def setDebugOff(self):	self._setFlag("debug", False)
	def isEnableCacheOn(self): return self._isFlagSet("enablecache", True)
	def setEnableCacheOn(self):	self._setFlag("enablecache", True)
	def setEnableCacheOff(self):	self._setFlag("enablecache", False)

##
#Provides a common interface for the Boxee player
#
class PlexeePlayer(object):
	def __init__(self, plexee):
		self.plexee = plexee
		self.shouldWait = True
		self.isPlayingTheme = False
		self.musicList = mc.PlayList(mc.PlayList.PLAYLIST_MUSIC)
		self.videoList = mc.PlayList(mc.PlayList.PLAYLIST_VIDEO)
	
	def stopWaiting(self):
		self.shouldWait = False
	
	def playTheme(self, item):
		#Check if user wants themes played
		if not self.plexee.config.isPlayThemesOn():
			return
		
		#If the player is already playing - and it's not another theme then don't play
		if mc.GetPlayer().IsPlaying() and not self.isPlayingTheme():
			return
			
		url = ""
		title = item.GetProperty("title")
		server = self.plexee.getItemServer(item)
		if not server:
			return
			
		themeKey = item.GetProperty("theme")
		if themeKey == "":
			themeKey = item.GetProperty("grandparenttheme")
		if themeKey == "":
			self.stopTheme()
			return
		machineIdentifier = item.GetProperty("machineidentifier")
		url = server.getUrl(themeKey)
		li = mc.ListItem(mc.ListItem.MEDIA_AUDIO_MUSIC)
		li.SetPath(url)
		li.SetTitle(title)
		li.SetLabel(title)
		li.SetProperty("machineidentifier", machineIdentifier)
		li.SetContentType("audio/mpeg")
		
		util.logDebug("Playing theme: %s, URL: %s" % (title, url))
		self.isPlayingTheme = True
		mc.GetPlayer().PlayInBackground(li)
		self.plexee.config.setPlayingThemeOn()

	def stopTheme(self):
		if self.isPlayingTheme:
			util.logDebug("Stopping theme")
			mc.GetPlayer().Stop()
			xbmc.sleep(200)
		self.isPlayingTheme = False
		self.plexee.config.setPlayingThemeOff()
			
	def getMusicPlaylist(self):	return self.musicList
	def getVideoPlaylist(self):	return self.videoList
	def clearMusicList(self): self.musicList.Clear()
	def clearVideoList(self): self.videoList.Clear()
		
	def addMusic(self, item):
		self.musicList.Add(item)

	def playMusicItems(self, items, startIndex = 0):
		self.stopTheme()
		self.clearMusicList()
		for item in items:
			self.addMusic(item)
		self.playMusicList(startIndex)
		
	def playVideoItems(self, items, startIndex = 0):
		self.stopTheme()
		self.clearVideoList()
		for item in items:
			self.addVideo(item)
		self.playVideoList(startIndex)

	def queueMusicItems(self, items, showQueueNotification = True):
		for item in items:
			self.addMusic(item)
			if showQueueNotification:
				mc.ShowDialogNotification("Queued track: "+item.GetTitle())

	def addVideo(self, item): self.videoList.Add(item)
	def playMusicList(self, index = 0, onPlay = None, args = None):
		self.stopTheme()
		self.musicList.Play(index)
		self.waitForPlayer(onPlay, args)
	def playVideoList(self, index = 0, onPlay = None, args = None):
		self.stopTheme()
		self.videoList.Play(index)
		self.waitForPlayer(onPlay, args)
	
	def pause(self):
		mc.GetPlayer().Pause()

	def _removeItem(self, playlist, items, removeIndex):
		playlist.Clear()
		for i in range(len(self.getContentList().GetItems())):
			if i != removeIndex:
				playlist.Add(self.getContentList().GetItem(i))
	
	def removeMusicItem(self, items, removeIndex): self._removeItem(self.musicList, items, removeIndex)
	def removeVideoItem(self, items, removeIndex): self._removeItem(self.videoList, items, removeIndex)
	
	def getCurrentMusicListItem(self): return self._getCurrentListItem(self.musicList)
	def getCurrentVideoListItem(self): return self._getCurrentListItem(self.videoList)
	def _getCurrentListItem(self, playlist): return playlist.GetItem(playlist.GetPosition())
	
	def getDisplayMusicList(self): return self._getDisplayList(self.musicList)
	def getDisplayVideoList(self): return self._getDisplayList(self.videoList)
	def _getDisplayList(self, playlist):
		childItems = mc.ListItems()
		for i in range(playlist.Size()):
			item = playlist.GetItem(i)
			item.SetProperty('position',str(i))
			thumbUrl = item.GetProperty("thumburl")
			if thumbUrl != "":
				item.SetThumbnail(thumbUrl)
				item.SetImage(0, thumbUrl)
			childItems.append(item)
		return childItems
	
	def waitForPlayer(self, onPlay, args):
		t = threading.Thread(target=self._waitForPlayer, args=(onPlay,args))
		t.start()
	
	def _waitForPlayer(self, onPlay, args):
		self.shouldWait = True
		#ok wait for player to start
		loopTimeout = 10*60 #Wait a maximum of 10 minutes
		loop = 0
		util.logDebug("Waiting on player...")
		while not xbmc.Player().isPlaying() and self.shouldWait:
			xbmc.sleep(1000)
			loop = loop + 1
			if loop > loopTimeout:
				break
		
		if loop <= loopTimeout and self.shouldWait:
			util.logDebug("Player started...")
			if onPlay != None:
				onPlay(args)
		elif not self.shouldWait:
			util.logDebug("Likely exited player...")
			xbmc.Player().stop()
		else:
			util.logDebug("Timed out waiting on Player to start - progress updating may not work...")	
	
##
#The core of the Plexee application
#	
class Plexee(object):
	"""
	Interface with Boxee system
	"""
	WINDOW_HOME_ID = 14000
	WINDOW_DIRECTORY_ID = 14001
	WINDOW_ALBUM_ID = 14003
	WINDOW_PLAYLIST_ID = 14004

	DIALOG_CONNECT_ID = 15002
	DIALOG_PHOTO_ID = 15003
	DIALOG_EXIT_ID = 14010
	DIALOG_SETTINGS_ID = 15000
	DIALOG_PLAY_ID = 15001
	DIALOG_USER_ID = 15004
	
	DIRECTORY_TITLE_ID = 100
	DIRECTORY_SECONDARY_ID = 200
	DIRECTORY_ITEMS_ID = 300

	PLAY_DIALOG_LIST_ID = 100
	SERIES_LIST_ID = 100
	PHOTO_DIALOG_LIST_ID = 100
	
	HOME_GROUPLIST_ID = 1000
	
	THUMB_WIDTH = 400
	THUMB_HEIGHT = 225
	ART_WIDTH = 980
	ART_HEIGHT = 580

	MENU_SECTIONS = "SECTION"
	MENU_DIRECT = "DIRECT"
	
	CORE_VIDEO_ATTRIBUTES = ['playlistType','machineIdentifier','viewGroup','title','ratingKey','key','thumb','art','theme','type','title1','title2','size','index','search','secondary','parentKey','duration','tag','grandparentTheme', 'librarySectionID', 'playlistItemID']
	ADDITIONAL_GENERAL_ATTRIBUTES = ['art','title','audioChannels','contentRating','year','summary','viewOffset','rating','tagline']
	ADDITIONAL_EPISODE_ATTRIBUTES = ['grandparentTitle','index','parentIndex','leafCount','viewedLeafCount']
	
	DISPLAY_AS_CONTENT = ["artist","album","photo","season","artist_search","person_search","albums"]
	
	def __init__(self):
		self.plexManager = plex.PlexManager()
		self.config = PlexeeConfig()
		self._windows = dict()
		self.player = PlexeePlayer(self)
		self.cache = PlexeeCache(self)
		self._windows[Plexee.WINDOW_HOME_ID] = PlexeeHomeWindow(self)
		self._windows[Plexee.WINDOW_ALBUM_ID] = PlexeeAlbumWindow(self)
		self._windows[Plexee.WINDOW_DIRECTORY_ID] = PlexeeDirectoryWindow(self)
		self._windows[Plexee.WINDOW_PLAYLIST_ID] = PlexeePlaylistWindow(self)
		self._windows[Plexee.DIALOG_SETTINGS_ID] = PlexeeSettingsDialog(self)
		self._windows[Plexee.DIALOG_CONNECT_ID] = PlexeeConnectionDialog(self)
		self._windows[Plexee.DIALOG_USER_ID] = PlexeeUserDialog(self)
		self._windows[Plexee.DIALOG_PLAY_ID] = PlexeePlayDialog(self)
		self._windows[Plexee.DIALOG_PHOTO_ID] = PlexeePhotoDialog(self)
		

	def getHomeWindow(self): return self._windows[Plexee.WINDOW_HOME_ID]
	def getDirectoryWindow(self): return self._windows[Plexee.WINDOW_DIRECTORY_ID]
	def getAlbumWindow(self): return self._windows[Plexee.WINDOW_ALBUM_ID]
	def getPlaylistWindow(self): return self._windows[Plexee.WINDOW_PLAYLIST_ID]
	def getSettingsDialog(self): return self._windows[Plexee.DIALOG_SETTINGS_ID]
	def getConnectionDialog(self): return self._windows[Plexee.DIALOG_CONNECT_ID]
	def getUserDialog(self): return self._windows[Plexee.DIALOG_USER_ID]
	def getPlayDialog(self): return self._windows[Plexee.DIALOG_PLAY_ID]
	def getPhotoDialog(self): return self._windows[Plexee.DIALOG_PHOTO_ID]

	def getItemServer(self, item):
		machineIdentifier = item.GetProperty("machineidentifier")
		return self.plexManager.getServer(machineIdentifier)
	
	def clearWindowState(self):
		for w in self._windows:
			win = self._windows[w]
			isHome = win.getId() == Plexee.WINDOW_HOME_ID
			if win.window:
				win.window.ClearStateStack(isHome)
	
	def getDisplayingCollection(self, clickedItem, titleItem):
		displayingCollection = titleItem.GetProperty("viewgroup")
		#Search
		if displayingCollection == "":
			type = clickedItem.GetProperty("type")
			if type == "person":
				displayingCollection = "person_search"
			elif type == "artist":
				displayingCollection = "artist_search"
			else:
				displayingCollection = type
			if displayingCollection == "":
				displayingCollection = clickedItem.GetProperty("itemtype").lower()
				
		#Forces items album, photo, season to be displayed as content
		isMenuCollection = (titleItem.GetProperty("ismenu") == "1")
		if isMenuCollection and displayingCollection not in Plexee.DISPLAY_AS_CONTENT:
			displayingCollection = "menu"
		return displayingCollection

	def getWindow(self, id):
		if not id in self._windows:
			return None
		return self._windows[id]
		
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

	def isEpisode(self, listItem): return listItem.GetProperty('type') == 'episode'
	def isSeason(self, listItem): return listItem.GetProperty('type') == 'season'
	def isShow(self, listItem): return listItem.GetProperty('type') == 'show'
		
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
		for a in (Plexee.ADDITIONAL_GENERAL_ATTRIBUTES + Plexee.ADDITIONAL_EPISODE_ATTRIBUTES):
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
		url = self._getThumbUrl(server, li)
		if url: li.SetImage(0, url)
		url = self._getArtUrl(server, li)
		if url: li.SetImage(1, url)
	
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
	
	#<Artist thumb="/music/iTunes/thumbs/album/48th%20Highlanders.Scotland%20the%20Brave%20-%20Bagpipes.jpg" titleSort="48th Highlanders" key="48th%20Highlanders" artist="48th Highlanders"/>
	def _createBaseItunesItem(self, server, element, sourceUrl):
		listItem = mc.ListItem(mc.ListItem.MEDIA_UNKNOWN)
		listItem.SetProperty("itemtype", element.tag)
		listItem.SetProperty("machineidentifier", util.cleanString(server.machineIdentifier))
		if element.attrib.has_key("key"):
			listItem.SetPath(server.joinUrl(sourceUrl, element.attrib["key"]))
			listItem.SetProperty("key",server.joinUrl(sourceUrl, element.attrib["key"]))
		listItem.SetProperty("thumb", util.cleanString(element.attrib["thumb"]))
		if element.attrib.has_key("thumb"):
			listItem.SetImage(0, self._getThumbUrl(server,listItem))
		propertyMap = ["track","album","artist","index","duration"]
		for property in propertyMap:
			if element.attrib.has_key(property):
				listItem.SetProperty(property, util.cleanString(element.attrib[property]))
		return listItem
		
	def _createItunesArtistItem(self, server, element, sourceUrl):
		listItem = self._createBaseItunesItem(server, element, sourceUrl)
		listItem.SetProperty("title", util.cleanString(element.attrib["artist"]))
		return listItem
	
	def _createItunesAlbumItem(self, server, element, sourceUrl):
		listItem = self._createBaseItunesItem(server, element, sourceUrl)
		listItem.SetProperty("title", util.cleanString(element.attrib["album"]))
		return listItem
	
	def _createItunesTrackItem(self, server, element, sourceUrl):
		listItem = self._createBaseItunesItem(server, element, sourceUrl)
		listItem.SetProperty("title", util.cleanString(element.attrib["track"]))
		duration = ""
		if element.attrib.has_key("totalTime") and element.attrib["totalTime"].isdigit():
			#Format millisecond duration
			duration = util.msToFormattedDuration(int(element.attrib["totalTime"]),False)
		listItem.SetProperty("durationformatted", duration)
		return listItem

	def _createListItem(self, server, element, sourceUrl, additionalAttributes = []):
		"""
		Create list items from the Plex server and URL to display
		"""
		isItunesPlugin = ("/music/itunes" in sourceUrl.lower())
		if isItunesPlugin:
			if element.tag == "Artist":
				return self._createItunesArtistItem(server, element, sourceUrl)
			elif element.tag == "Album":
				return self._createItunesAlbumItem(server, element, sourceUrl)
			elif element.tag == "Track":
				return self._createItunesTrackItem(server, element, sourceUrl)
			
		# Important Properties
		listItem = mc.ListItem(mc.ListItem.MEDIA_UNKNOWN)
		listItem.SetProperty("itemtype", element.tag)
		listItem.SetProperty("machineidentifier", util.cleanString(server.machineIdentifier))
		if element.attrib.has_key("key"):
			listItem.SetPath(server.joinUrl(sourceUrl, element.attrib["key"]))
	
		#for attribute in (Plexee.CORE_VIDEO_ATTRIBUTES + additionalAttributes):
		for attribute in element.keys():
			#if element.attrib.has_key(attribute):
			#util.logDebug('Property [%s]=[%s]' % (attribute.lower(), util.cleanString(element.attrib[attribute])))
			listItem.SetProperty(attribute.lower(), util.cleanString(element.attrib[attribute]))

		if (self.isSeason(listItem) or self.isShow(listItem)) and listItem.GetProperty("leafcount") != "" and listItem.GetProperty("viewedleafcount") != "":
			count = int(listItem.GetProperty("leafcount")) - int(listItem.GetProperty("viewedleafcount"))
			listItem.SetProperty("unwatchedcount", str(count)) 
			
		#Special titles
		if self.isEpisode(listItem):
			epTitle = util.formatEpisodeTitle(season="", episode=listItem.GetProperty('index'), title=listItem.GetProperty('title'))
			listItem.SetProperty("title",epTitle)
			#is it watched?
			data, u = server.getData(listItem.GetProperty("key"))
			if data:
				vals = ElementTree.fromstring(data)[0]
				if not vals.attrib.has_key("viewCount"):
					listItem.SetProperty("notviewed","1")
		
		if listItem.GetProperty('type') == 'track':
			#Duration
			duration = ""
			if element.attrib.has_key("duration") and element.attrib["duration"].isdigit():
				#Format millisecond duration
				duration = util.msToFormattedDuration(int(element.attrib["duration"]),False)
			listItem.SetProperty("durationformatted", duration)
		
		# Image paths
		thumbUrl = ""
		if listItem.GetProperty('thumb') != "":
			thumbUrl = self._getThumbUrl(server, listItem)
		elif listItem.GetProperty('art') != "":
			thumbUrl = self._getThumbUrl(server, listItem, "art")
		listItem.SetProperty("thumburl", thumbUrl)
		
		if thumbUrl != "":
			#listItem.SetThumbnail(thumbUrl)
			listItem.SetImage(0, thumbUrl)
			
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
			attribs = ['machineidentifier','viewGroup','summary','id','title','key','thumb','type','title1','title2','size','index','search','secondary','parentKey','art']
			for attribute in attribs:
				if child.attrib.has_key(attribute):
					#util.logDebug('Property [%s]=[%s]' % (attribute.lower(), util.cleanString(element.attrib[attribute])))
					listItem.SetProperty(attribute.lower(), util.cleanString(child.attrib[attribute]))
			# Image paths
			# if child.attrib.has_key("thumb"):
				# listItem.SetImage(0, listItem.GetProperty("thumb"))
			# elif child.attrib.has_key("art"):
				# listItem.SetImage(0, listItem.GetProperty("art"))
				
				
			childListItems.append(listItem)

		return childListItems

	def getMenuItems(self, server, type, key):
		data = ""
		url = ""
		if type == Plexee.MENU_SECTIONS:
			data, url = server.getSectionData(key)
		elif type == Plexee.MENU_DIRECT:
			data, url = server.getData(key)
		util.logDebug("Updating menu using data from url "+url)
		return self.getListItems(server, data, url).childListItems

	def getListItems(self, server, data, sourceUrl, titleListItem = None, additionalAttributes = []):
		"""
		Create items to display from a Plex server
		"""
		if not data:
			return None
		dataHash = util.hash(data)
		windowInformation = self.cache.getItem(sourceUrl, dataHash)
		if windowInformation:
			return windowInformation

		tree = ElementTree.fromstring(data)
		if not titleListItem:
			titleListItem = self._createListItem(server, tree, sourceUrl)
			
		titleListItem.SetProperty("plexeeview", "grid")
		
		#Set title item art/thumb to display if needed
		titleListItem.SetProperty("art", tree.attrib.get("art",""))
		titleListItem.SetProperty("thumb", tree.attrib.get("thumb",""))
		dataHash = util.hash(data)
		titleListItem.SetProperty("hash", dataHash)
		
		childListItems = mc.ListItems()
		hasChildDirectories = True
		childItems = ["Directory","Photo","Album"]
		#If all directories (with no duration) treat as menu
		for child in tree:
			childListItem = self._createListItem(server, child, sourceUrl, additionalAttributes)
			childListItems.append(childListItem)
			hasChildDirectories = (hasChildDirectories and childListItem.GetProperty("itemtype") in childItems and childListItem.GetProperty("duration") == "")

		#If collection of directories then this looks like a menu
		if titleListItem.GetProperty("viewgroup") == "secondary":
			titleListItem.SetProperty("ismenu", "1")
		elif hasChildDirectories:
			titleListItem.SetProperty("ismenu", "1")
		
		windowInformation = WindowInformation(titleListItem, childListItems, dataHash)
		self.cache.addItem(sourceUrl, windowInformation)
		return windowInformation

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
	
	def getMultiUserItems(self, machineID):
		"""
		Create user items from MyPlex
		"""
		data = self._myplex().getMultiUserData()
		if not data:
			return mc.ListItems()
		tree = ElementTree.fromstring(data)
		childListItems = mc.ListItems()
		for child in tree:
			#Check servers
			found = False
			for server in child.findall("Server"):
				if server.attrib["machineIdentifier"] == machineID:
					found = True
					break
			if not found:
				continue
			listItem = mc.ListItem(mc.ListItem.MEDIA_UNKNOWN)
			listItem.SetProperty("itemtype", "UserItem")
			listItem.SetPath('1')
			#id="8056244" title="Kids" thumb="https://plex.tv/users/2194dc57a32e2b6d/avatar"
			attribs = ['id','title','thumb']
			for attribute in attribs:
				if child.attrib.has_key(attribute):
					#util.logDebug('Property [%s]=[%s]' % (attribute.lower(), util.cleanString(element.attrib[attribute])))
					listItem.SetProperty(attribute.lower(), util.cleanString(child.attrib[attribute]))
			childListItems.append(listItem)
		return childListItems        

	def monitorPlayback(self, args):
		"""
		Update the played progress every 5 seconds while the player is playing
		"""
		server = args['server']
		key = args['key']
		offset = args['offset']
		subtitleKey = args['subtitleKey']
		totalTimeSecs = args['totalTimeSecs']
		isDirectStream = args['isDirectStream']
		
		if offset != 0:
			util.logDebug("Seeking to resume position: "+str(offset))
			xbmc.Player().seekTime(offset)
		
		if subtitleKey != "":
			util.logInfo("Setting subtitles to: " + subtitleKey)
			try:
				xbmc.Player().setSubtitles(subtitleKey)
			except:
				util.logError("Error setting subtitle key=[%s]: %s" % (str(subtitleKey), sys.exc_info()[0]))
				mc.ShowDialogNotification("Failed to set subtitles")
		
		progress = 0
		util.logDebug("Monitoring playback to update progress...")
		#Whilst the file is playing back
		player = mc.GetPlayer()
		isWatched = False
		while player.IsPlaying():
			#Get the current playback time
			currentTimeSecs = int(player.GetTime())
			
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
		self.player.clearVideoList()
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
			li.SetDescription(description, False)
			li.SetContentRating(contentRating)
			
			#TV Episode extras
			mediaType = videoNode.attrib.get("type","movie")
			if mediaType == 'episode':
				li.SetTVShowTitle(util.cleanString(videoNode.attrib.get("grandparentTitle","")))
				li.SetEpisode(int(videoNode.attrib.get('index')))
				li.SetSeason(int(videoNode.attrib.get('parentIndex')))
			
			self.player.addVideo(li)
			util.logInfo("Added item to play: "+li.GetPath())
			partIndex = partIndex + 1

		subtitleKey = ""
		#Set subtitles
		if subtitleIndex != 0:
			for s in mediaNode.findall("Part/Stream"):
				if s.attrib.get("id") != str(subtitleIndex):
					continue;
				subtitleKey = server.getUrl(s.attrib.get("key"))
			
		if subtitleKey == "":
			subtitleKey = os.path.join(mc.GetApp().GetAppMediaDir(), 'media', 'no_subs.srt')
		key = videoNode.attrib.get('ratingKey')
		args = dict()
		args['server'] = server
		args['key'] = key
		args['offset'] = offset
		args['subtitleKey'] = subtitleKey
		args['totalTimeSecs'] = totalTimeSecs
		args['isDirectStream'] = False
		self.player.playVideoList(onPlay=self.monitorPlayback,args=args)
	
	def queueVideoItem(self, server, item):
		self.playVideoItem(server, item, 0, 0, 0, 0, True)
		
	def playVideoItem(self, server, playItem,  mediaIndex, subtitleIndex, audioIndex, offset=0, queueOnly = False):
		"""
		Play the video item
		"""
		util.logDebug("Play video item")
		data, url = server.getData(playItem.GetPath())
		if not data:
			return None
		
		isDirectStream = False
		if offset != 0:
			offset = offset/1000

		tree = ElementTree.fromstring(data)
		videoNode = tree[0]
		if not queueOnly:
			self.player.clearVideoList()

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
			li.SetProperty('title',title)
			
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
					server.setAudioStream(self.plexManager, partId, str(audioIndex))
					server.setSubtitleStream(self.plexManager, partId, str(subtitleIndex))
					
					url = server.getVideoDirectStreamUrl(self.plexManager, videoId, mediaIndex, partIndex, offset)
					li.SetPath("playlist://"+urllib.quote_plus(url)+"?quality=A")
					li.SetContentType('application/vnd.apple.mpegurl')
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
			
			self.player.addVideo(li)
			partIndex = partIndex + 1

		subtitleKey = ""
		if not isDirectStream:
			#Set subtitles
			if subtitleIndex != 0:
				for s in mediaNode.findall("Part/Stream"):
					if s.attrib.get("id") != str(subtitleIndex):
						continue;
					subtitleKey = server.getUrl(s.attrib.get("key"))
				
			if subtitleKey == "":
				subtitleKey = os.path.join(mc.GetApp().GetAppMediaDir(), 'media', 'no_subs.srt')
		key = videoNode.attrib.get('ratingKey')

		if not queueOnly:
			args = dict()
			args['server'] = server
			args['key'] = key
			args['offset'] = offset
			args['subtitleKey'] = subtitleKey
			args['totalTimeSecs'] = totalTimeSecs
			args['isDirectStream'] = isDirectStream
			
			self.player.playVideoList(onPlay=self.monitorPlayback,args=args)
		else:
			return

	def createAndAddMusicItem(self, items, listItem):
		url = listItem.GetPath()
		server = self.getItemServer(listItem)
		isItunesTrack = False
		
		if listItem.GetProperty("track") == "":
			track = server.getPlexItem(url)
			if not track:				
				return None
			album = server.getPlexParent(track)
			artist = server.getPlexParent(album)

			album = album.attrib.get("title","")
			artist = artist.attrib.get("title","")
			title = track.attrib.get("title", "Plex Track")
		else:
			#Itunes track
			isItunesTrack = True
			title = listItem.GetProperty("track")
			album = listItem.GetProperty("album")
			artist = listItem.GetProperty("artist")
			
		if isItunesTrack:
			li = mc.ListItem(mc.ListItem.MEDIA_AUDIO_MUSIC)
			li.SetAlbum(album)
			li.SetArtist(artist)
			li.SetTitle(title)
			li.SetProperty('title', title)
			li.SetProperty('index', listItem.GetProperty('index'))
			li.SetProperty('durationformatted', listItem.GetProperty('durationformatted'))
			li.SetProperty('art', listItem.GetProperty('art'))
			li.SetProperty('thumb', listItem.GetProperty('thumb'))
			li.SetProperty('thumburl', listItem.GetProperty('thumburl'))
			#li.SetThumbnail(listItem.GetThumbnail())
			li.SetProperty('key', listItem.GetProperty('key'))
			li.SetProperty('machineidentifier', listItem.GetProperty('machineidentifier'))
			li.SetLabel(title)
			li.SetPath(listItem.GetProperty('key'))
			items.append(li)
		else:
			for part in track.findall("Media/Part"):
				li = mc.ListItem(mc.ListItem.MEDIA_AUDIO_MUSIC)
				li.SetAlbum(album)
				li.SetArtist(artist)
				li.SetTitle(title)
				li.SetProperty('title', title)
				li.SetProperty('index', listItem.GetProperty('index'))
				li.SetProperty('durationformatted', listItem.GetProperty('durationformatted'))
				li.SetProperty('art', listItem.GetProperty('art'))
				li.SetProperty('thumb', listItem.GetProperty('thumb'))
				li.SetProperty('thumburl', listItem.GetProperty('thumburl'))
				#li.SetThumbnail(listItem.GetThumbnail())
				li.SetProperty('key', listItem.GetProperty('key'))
				li.SetProperty('machineidentifier', listItem.GetProperty('machineidentifier'))
				li.SetLabel(title)
				li.SetPath(server.getUrl(part.attrib.get('key')))
				items.append(li)
	
	def getPhotoList(self, listItem):
		"""
		Return a list of all photo items
		"""
		server = self.getItemServer(listItem)
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
		items = mc.ListItems()
		self.createAndAddMusicItem(items, listItem)
		#Play or queue
		if mc.GetPlayer().IsPlayingAudio() and self.config.isQueueAudioOn():
			self.player.queueMusicItems(items)
		else:
			self.player.playMusicItems(items)

	def activateWindow(self, id):
		util.logDebug("Activate window %s started" % id)
		mc.ActivateWindow(id)
		util.logDebug("Activate window %s ended" % id)
		return mc.GetWindow(id)

	def _handlePhotoItem(self, listItem):
		list = self.getPhotoList(listItem)
		if list != None:
			window = self.getPhotoDialog()
			window.activate()
			window.photoList.SetItems(list)
			window.photoList.SetFocusedItem(util.getIndex(listItem, list))
		else:
			mc.ShowDialogNotification("Unable to display picture")

	def _handleVideoItem(self, listItem, fromWindowId):
		"""
		Show play screen for video item
		"""
		mc.ShowDialogWait()
		
		server = self.getItemServer(listItem)
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
		
		if fromWindowId == Plexee.WINDOW_HOME_ID:
			#Clicked on Movie etc.. from home menu
			#Grab the menu items - and go to the first one
			url = menuItems[0].GetPath()
			data, url = server.getData(url)
			directoryWindow = self.getDirectoryWindow()
			windowInformation = self.getListItems(server, data, url)
			directoryWindow.activate(clickedItem, server)
			directoryWindow.updateMenuItems(menuItems)
			directoryWindow.updateContentItems(windowInformation)
		else:
			#Stay in same window, push state
			directoryWindow = self.getWindow(fromWindowId)
			if directoryWindow:
				directoryWindow.activate(clickedItem, server)
				directoryWindow.updateMenuItems(menuItems)
		mc.HideDialogWait()
		return True

	def _getArtUrl(self, server, listItem):
		art = listItem.GetProperty("art")
		if art:
			util.logDebug("Art: "+art)
			return server.getThumbUrl(art, self.ART_WIDTH, self.ART_HEIGHT)
		else:
			return False
		
	def _getThumbUrl(self, server, listItem, property="thumb"):
		key = listItem.GetProperty(property)
		if key:
			util.logDebug("Thumb: " + key)
			return server.getThumbUrl(key, self.THUMB_WIDTH, self.THUMB_HEIGHT)
		else:
			return False

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
			server = self.getItemServer(clickedItem)

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

			titleItem = windowInformation.titleListItem
			isMenuCollection = (titleItem.GetProperty("ismenu") == "1")
			isFromHomeWindow = (fromWindowId == Plexee.WINDOW_HOME_ID)
			
			"""Set the display collection type"""
			displayingCollection = self.getDisplayingCollection(clickedItem, titleItem)

			"""Set the target window"""
			directoryWindow = None
			if displayingCollection == "track":
				directoryWindow = self.getAlbumWindow()
			else:
				directoryWindow = self.getDirectoryWindow()

			isWindowChanging = (fromWindowId != directoryWindow.getId())
			menuItems = None
			
			if not isWindowChanging and isMenuCollection and not isFromHomeWindow:
				directoryWindow.pushState()

			"""Debug"""
			if self.config.isDebugOn():
				msg = "Displaying Collection: %s, ViewGroup: %s, FromWindowId: %s, NextWindowId: %s" % (displayingCollection, titleItem.GetProperty("viewgroup"), str(fromWindowId), str(directoryWindow.getId()))
				util.logDebug(msg)

			if displayingCollection == "menu":
				"""Menu collection"""
				return self._handleMenuItem(server, clickedItem, windowInformation, fromWindowId)
				
			elif displayingCollection == "season":
				"""Displaying TV Show Seasons"""
				if not titleItem.GetImage(0): titleItem.SetImage(0, self._getArtUrl(server, titleItem))
				titleItem.SetImage(1, self._getArtUrl(server, titleItem))
				self.player.playTheme(windowInformation.titleListItem)
			
			elif displayingCollection == "artist_search":
				"""Displaying Artist"""
				if not titleItem.GetImage(0): titleItem.SetImage(0, self._getArtUrl(server, titleItem))
				titleItem.SetImage(1, self._getArtUrl(server, titleItem))
				key = clickedItem.GetProperty('librarysectionid')
				menuItems = self.getMenuItems(server, Plexee.MENU_SECTIONS, key)
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
				menuItems = mc.ListItems()
				titleItem.SetProperty("title2", clickedItem.GetProperty("title"))

			elif displayingCollection == "episode":
				"""Episodes (in a Season)"""
				if not isFromHomeWindow:
					directoryWindow.pushState()
				else:
					self.player.playTheme(windowInformation.titleListItem)
				if not titleItem.GetImage(0): titleItem.SetImage(0, self._getArtUrl(server, titleItem))
				titleItem.SetImage(1, self._getArtUrl(server, titleItem))
				#Set the menu to the list of all seasons
				key = clickedItem.GetProperty('parentkey')+"/children"
				menuItems = self.getMenuItems(server, Plexee.MENU_DIRECT, key)
					
			elif displayingCollection == "track":
				"""Tracks (in an Album)"""
				if not titleItem.GetImage(0): titleItem.SetImage(0, self._getArtUrl(server, titleItem))
				titleItem.SetImage(1, self._getArtUrl(server, titleItem))
				#Set the menu to the list of all albums
				key = clickedItem.GetProperty('parentkey')
				if key != "":
					menuItems = self.getMenuItems(server, Plexee.MENU_DIRECT, key+"/children")
				else:
					path = clickedItem.GetPath()
					if path.endswith("allLeaves"):
						menuItems = self.getMenuItems(server, Plexee.MENU_DIRECT, path.replace("allLeaves","children"))

			else:
				"""All other collections"""
				pass
			
			#Update the new/current window content
			if isWindowChanging:
				directoryWindow.activate(clickedItem, server)
			directoryWindow.hide()
			if menuItems != None:
				directoryWindow.updateMenuItems(menuItems)
			directoryWindow.updateContentItems(windowInformation)
				
		finally:
			mc.HideDialogWait()
		
	def playVideo(self, server, playItem, mediaIndex, subtitleIndex, audioIndex):
		#util.logDebug("Playing item "+playItem.GetProperty("title"))
		
		if subtitleIndex != 0 and audioIndex != 0:
			#Transcoding will occurred
			selection = mc.ShowDialogConfirm("Transcoding required", "Selecting subtitles and a different audio track requires transcoding. This may take a while depending on the media and Plex server. "+os.linesep+os.linesep+"Do you wish to continue?", "No", "Yes")
			if not selection:
				mc.HideDialogWait()
				return False
		
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
				mc.HideDialogWait()
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
			connectDialog = self.getConnectionDialog()
			connectDialog.activate()

##
#Represents the content of a PlexeeDirectoryWindow
#The title item and associated content items
#			
class WindowInformation(object):
	def __init__(self, titleListItem, childListItems, dataHash):
		self.titleListItem = titleListItem
		self.childListItems = childListItems
		self.dataHash = dataHash

##
#Represents media options available for a video
#i.e. available video resolutions, audio streams, subtitles
#	
class MediaOptions(object):
	def __init__(self, mediaItems, subtitleItems, audioItems):
		self.mediaItems = mediaItems
		self.subtitleItems = subtitleItems
		self.audioItems = audioItems
		