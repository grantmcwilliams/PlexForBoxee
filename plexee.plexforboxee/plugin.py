import mc
import plexee
import util
import urllib
import time
import xbmc
from plexgdm import PlexGDM

### Detect and set Plex Servers

def showConnectionWindow():
	mc.ActivateWindow(CONNECT_DIALOG_ID)

def showNextError():
	msg = manager.getNextConnectionError()
	mc.GetWindow(CONNECT_DIALOG_ID).GetLabel(300).SetLabel(msg)
	
def updateConnectionResult():
	msg = manager.getNextConnectionError()
	mc.GetWindow(CONNECT_DIALOG_ID).GetLabel(300).SetVisible(True)
	mc.GetWindow(CONNECT_DIALOG_ID).GetLabel(300).SetLabel(msg)
	mc.GetWindow(CONNECT_DIALOG_ID).GetButton(402).SetVisible(True)

	if len(manager.connectionErrors) > 1:
		mc.GetWindow(CONNECT_DIALOG_ID).GetControl(401).SetVisible(True)
		mc.GetWindow(CONNECT_DIALOG_ID).GetButton(401).SetFocus()
	else:
		mc.GetWindow(CONNECT_DIALOG_ID).GetButton(402).SetFocus()
	
	
def initPlexee():
	manager.clearServers()
	manager.clearMyPlex()
	
	manager.clearConnectionErrors()
	
	if not config.GetValue("usediscover") and not config.GetValue("usemanual") and not config.GetValue("usemyplex"):
		loadContent()
		return

	showConnectionWindow()
	
	try:
		mc.ShowDialogWait()

		#try manual server
		if config.GetValue("usemanual"):
			host = config.GetValue("manualhost")
			port = config.GetValue("manualport")
			manager.addMyServer(host, port)
			if not manager.myServers:
				#Manual set but no server found
				manager.addConnectionError("Failed to connect to plex server: "+host+":"+port+"[CR][CR]Check the server IP and port is correct.")

		#try GDM auto discovery
		if config.GetValue("usediscover"):
			discoverTime = config.GetValue("discoverTime")
			if not discoverTime or not discoverTime.isdigit():
				#Set default value to 1 seconds timeout for auto-discovery
				config.SetValue("discoverTime", "1")
				discoverTime = 1
			discoverTime = int(discoverTime)
				
			serverList = PlexGDM().getServers(discoverTime);
			if serverList:
				#GDM servers found
				for serverKey in serverList:
					manager.addMyServer(serverList[serverKey]['ip'], serverList[serverKey]['port'])
			else:
				#GDM enabled - but no servers found
				manager.addConnectionError("GDM - No servers found!" + \
					"[CR]" + \
					"[CR]1. Check that GDM is enabled on your Plex Server (you may need to restart the server)." + \
					"[CR]2. Check connectivity GDM broadcasts over UDP on port 32414" + \
					"[CR]3. Try increasing the GDM response time in the settings screen" + \
					"[CR][CR]Otherwise use the Manual Server or MyPlex options in the settings screen.")

		#try MyPlex
		if config.GetValue("usemyplex"):
			username = config.GetValue("myplexusername")
			passsword = config.GetValue("myplexpassword")
			if username and passsword:
				result = manager.myPlexLogin(username, passsword)
				if result == manager.ERR_NO_MYPLEX_SERVERS:
					manager.addConnectionError("No registered MyPlex servers to connect to")
				elif result == manager.ERR_MPLEX_CONNECT_FAILED:
					manager.addConnectionError("Unable to connect to any MyPlex registered servers.[CR][CR]Please check MyPlex for the server details and check connectivity.")
				elif result == manager.ERR_MYPLEX_NOT_AUTHENTICATED:
					manager.addConnectionError("Failed to connect to MyPlex.[CR][CR]Authentication failed - check your username and password")

		if len(manager.connectionErrors) > 0:
			#An Error Occurred
			updateConnectionResult()
		else:
			#No errors
			xbmc.executebuiltin("Dialog.Close("+str(CONNECT_DIALOG_ID)+")")

		loadContent()

	finally:
		mc.HideDialogWait()
			

def loadContent():
	window = mc.GetWindow(getWindowID("home"))
	myLibrary = window.GetList(110)
	sharedLibraries = window.GetList(210)
	myChannels = window.GetList(310)
	myRecentlyAdded = window.GetList(410)
	myOnDeck = window.GetList(510)

	myLibrary.SetItems(manager.getMyLibrary())
	sharedLibraries.SetItems(manager.getSharedLibraries())
	myChannels.SetItems(manager.getMyChannels())
	myRecentlyAdded.SetItems(manager.getMyRecentlyAdded())
	myOnDeck.SetItems(manager.getMyOnDeck())
	
	window.GetControl(1000).SetFocus()

			
def loadHome():
	mc.ActivateWindow(getWindowID("home"))

"""
Play track
"""
def _handleTrackItem(listItem):
	url = listItem.GetPath()
	machineIdentifier = listItem.GetProperty("machineidentifier")
	manager.playMusicUrl(machineIdentifier, url)

def _handlePhotoItem(listItem):
	url = listItem.GetPath()
	machineIdentifier = listItem.GetProperty("machineidentifier")
	util.logDebug("Photo URL " + url)
	list = manager.getPhotoList(machineIdentifier, url)
	if list != None:
		mc.ActivateWindow(PHOTO_DIALOG_ID)
		mc.GetWindow(PHOTO_DIALOG_ID).GetList(PHOTO_DIALOG_LIST_ID).SetItems(list)
	else:
		mc.ShowDialogNotification("Unable to display picture")

	
"""
Show play screen for video item
"""
def _handleVideoItem(listItem):
	mc.ShowDialogWait()
	machineIdentifier = listItem.GetProperty("machineidentifier")
	#Create a new list item with the additional video data
	server = manager.getServer(listItem.GetProperty("machineIdentifier"));
	
	#Get additional meta data for item to play
	li = server.getVideoItem(listItem)
	listItems = mc.ListItems()
	listItems.append(li)

	#Load any subtitles
	subItems = server.getSubtitles(li.GetPath())
	
	#Show play window
	mc.ActivateWindow(PLAY_DIALOG_ID)
	mc.GetWindow(PLAY_DIALOG_ID).GetList(PLAY_DIALOG_LIST_ID).SetItems(listItems)
	mc.GetWindow(PLAY_DIALOG_ID).GetList(310).SetItems(subItems)
	mc.HideDialogWait()

"""
Handles clicking on a menu option
"""
def _handleMenuItem(listItem, fromWindowId):
	url = listItem.GetPath()
	
	# Handle search items
	if listItem.GetProperty("search") == "1":
		search = mc.ShowDialogKeyboard(listItem.GetProperty("prompt"), "", False)
		if search:
			url += "&query=" + urllib.quote(search)
		else:
			return

	mc.ShowDialogWait()
	machineIdentifier = listItem.GetProperty("machineidentifier")
	windowInformation = manager.getListItems(machineIdentifier, url)
	viewGroup = windowInformation.titleListItems[0].GetProperty("viewgroup")
	nextWindowID = getWindowID(viewGroup)
	window = mc.GetActiveWindow()
	
	if fromWindowId != getWindowID('home'):
		if not (listItem.GetProperty('type') == "" and listItem.GetProperty('secondary') == ""):
			#Not a menu item with no secondary elements
			mc.GetActiveWindow().PushState()

	if viewGroup == "secondary":
		menuItems = windowInformation.childListItems
		if fromWindowId == getWindowID('home'):
			#Clicked on Movie etc.. from home menu
			#Grab the menu items - and go to the first one
			url = menuItems[0].GetPath()
			windowInformation = manager.getListItems(machineIdentifier, url)
			window = activateWindow(nextWindowID)
			updateMenuItems(window, menuItems)
			updateWindowItems(window, windowInformation)
		
		else:
			#Only found more menu items, so update them
			updateMenuItems(window, menuItems)
	
	else:
		#Found a list of items to display
		if fromWindowId == getWindowID('home'):
			#We need a window to update
			window = activateWindow(nextWindowID)
			#This means we have no menu items
		
		updateWindowItems(window, windowInformation)
		
	mc.HideDialogWait()

	
"""
Determines the appropriate action for a plex item (a url)
"""	
def handleItem(listItem, fromWindowId = 0):
	itemType = listItem.GetProperty("itemtype")

	if itemType == "Video":
		_handleVideoItem(listItem)
	
	elif itemType == "Track":
		_handleTrackItem(listItem)
	
	#Clicked on directory item
	elif itemType == "Directory":
		_handleMenuItem(listItem, fromWindowId)
		
	elif itemType == "Photo":
		_handlePhotoItem(listItem)
		
	# Unknown item
	else:
		mc.ShowDialogNotification("Unknown itemType: %s" % itemType)



def clearItems():
	window = mc.GetActiveWindow()
	blankItems = mc.ListItems()

	window.GetList(DIRECTORY_TITLE_ID).SetItems(blankItems)
	window.GetList(DIRECTORY_ITEMS_ID).SetItems(blankItems)
	#if clearSecondary: window.GetList(DIRECTORY_SECONDARY_ID).SetItems(blankItems)

def updateMenuItems(window, menuItems):
	window.GetList(DIRECTORY_SECONDARY_ID).SetItems(menuItems)
	
def updateWindowItems(window, windowInformation):
	window.GetList(DIRECTORY_TITLE_ID).SetItems(windowInformation.titleListItems)
	window.GetList(DIRECTORY_ITEMS_ID).SetItems(windowInformation.childListItems)
	if len(windowInformation.childListItems) > 0 and windowInformation.childListItems[0].GetLabel() != "":
		mc.ShowDialogNotification(windowInformation.childListItems[0].GetLabel())
	window.GetControl(DIRECTORY_ITEMS_ID).SetFocus()

def getActiveWindowID():
	return mc.GetActiveWindow().GetEdit(1).GetText()
		
def getWindowID(view):
	return WINDOW_IDS.get(view, 14001)
	
def activateWindow(id):
	mc.ActivateWindow(id)
	return mc.GetWindow(id)
	
# ENTRY POINT ##################################################################
if ( __name__ == "__main__" ):

	WINDOW_IDS = {
		"home": 14000,
		"default": 14001,
		"episode": 14002
	}

	DIRECTORY_TITLE_ID = 100
	DIRECTORY_SECONDARY_ID = 200
	DIRECTORY_ITEMS_ID = 300

	SETTINGS_DIALOG_ID = 15000
	PLAY_DIALOG_ID = 15001
	PLAY_DIALOG_LIST_ID = 100
	SERIES_LIST_ID = 100
	CONNECT_DIALOG_ID = 15002
	PHOTO_DIALOG_ID = 15003
	PHOTO_DIALOG_LIST_ID = 100

	manager = plexee.PlexeeManager()
	app = mc.GetApp()
	config = app.GetLocalConfig()
	
	#Jinxo: Set debug on to get all debug messages
	#config.SetValue("debug", "1")
	
	#default to autodiscover on first start of application
	if not config.GetValue("usemanual") and not config.GetValue("usediscover") and not config.GetValue("usemyplex"):
		config.SetValue("usediscover", "1")

	#default auto discovery time to 1 seconds
	discoverTime = config.GetValue("discovertime")
	if not discoverTime or not discoverTime.isdigit():
		config.SetValue("discovertime", "1")
	
	#startup
	loadHome()
	initPlexee()
