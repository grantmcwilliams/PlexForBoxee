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
	
def handleItem(listItem, fromWindowId = 0):
	global secondaryListItems
	itemType = listItem.GetProperty("itemtype")
	url = listItem.GetPath()

	# Handle search items
	if listItem.GetProperty("search") == "1":
		search = mc.ShowDialogKeyboard(listItem.GetProperty("prompt"), "", False)
		if search:
			url += "&query=" + urllib.quote(search)
		else:
			return

	# Load screen of items
	if itemType == "Directory":
		mc.ShowDialogWait()
		
		# load next screen information
		machineIdentifier = listItem.GetProperty("machineidentifier")
		windowInformation = manager.getListItems(machineIdentifier, url)
		viewGroup = windowInformation.titleListItems[0].GetProperty("viewgroup")
		nextWindowID = getWindowID(viewGroup)
		
		# save the state if needed
		if nextWindowID == fromWindowId:
			mc.GetActiveWindow().PushState()
		
		# secondary items
		if viewGroup == "secondary":
			secondaryListItems = windowInformation.childListItems
			if fromWindowId == getWindowID('home'):
				handleItem(windowInformation.childListItems[0])
			else:
				#clearItems()
				window = mc.GetActiveWindow()
				showWindowInformation(window, windowInformation)
		else:
			# start the new window
			window = activateWindow(nextWindowID)
			showWindowInformation(window, windowInformation)

	# Play video
	elif itemType == "Video":
		machineIdentifier = listItem.GetProperty("machineidentifier")
		windowInformation = manager.getListItems(machineIdentifier, url)

		#Set images for play window
		server = manager.getServer(listItem.GetProperty("machineIdentifier"));
		art = listItem.GetProperty("art")
		thumb = listItem.GetProperty("thumb")

		li = windowInformation.childListItems[0];
		titleLi = windowInformation.titleListItems[0];
		
		if art == "":
			art = li.GetProperty("art")

		if thumb != "":
			li.SetImage(1, server.getThumbUrl(thumb, 450, 500))
			
		if art != "":
			li.SetImage(2, server.getThumbUrl(art, 980, 580))
		
		#Load any subtitles
		subItems = server.getSubtitles(listItem.GetPath())
		mc.ActivateWindow(PLAY_DIALOG_ID)
		mc.GetWindow(PLAY_DIALOG_ID).GetList(PLAY_DIALOG_LIST_ID).SetItems(windowInformation.childListItems)
		mc.GetWindow(PLAY_DIALOG_ID).GetList(310).SetItems(subItems)
	
	elif itemType == "Track":
		machineIdentifier = listItem.GetProperty("machineidentifier")
		manager.playMusicUrl(machineIdentifier, url)
	
	# Unknown item
	else:
		mc.ShowDialogNotification("Unknown itemType: %s" % itemType)

	mc.HideDialogWait()

def clearItems():
	window = mc.GetActiveWindow()
	blankItems = mc.ListItems()

	window.GetList(DIRECTORY_TITLE_ID).SetItems(blankItems)
	window.GetList(DIRECTORY_ITEMS_ID).SetItems(blankItems)
	#if clearSecondary: window.GetList(DIRECTORY_SECONDARY_ID).SetItems(blankItems)

def showWindowInformation(window, windowInformation):
	viewGroup = windowInformation.titleListItems[0].GetProperty("viewgroup")

	if viewGroup == "secondary":
		window.GetList(DIRECTORY_SECONDARY_ID).SetItems(windowInformation.childListItems)
	else:
		window.GetList(DIRECTORY_TITLE_ID).SetItems(windowInformation.titleListItems)
		window.GetList(DIRECTORY_ITEMS_ID).SetItems(windowInformation.childListItems)
		if len(windowInformation.childListItems) > 0 and windowInformation.childListItems[0].GetLabel() != "":
			mc.ShowDialogNotification(windowInformation.childListItems[0].GetLabel())
		window.GetControl(DIRECTORY_ITEMS_ID).SetFocus()

def getActiveWindowID():
	return mc.GetActiveWindow().GetEdit(1).GetText()
		
def getWindowID(view):
	return WINDOW_IDS.get(view, 14001)
	
def loadSecondaryItems():
	global secondaryListItems
	
	if secondaryListItems:
		#mc.ShowDialogNotification("has secondary")
		mc.GetActiveWindow().GetList(200).SetItems(secondaryListItems)
	else:
		#mc.ShowDialogNotification("no secondary")
		mc.GetActiveWindow().GetList(200).SetItems(mc.ListItems())
	
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
	
	secondaryListItems = None
	manager = plexee.PlexeeManager()
	app = mc.GetApp()
	config = app.GetLocalConfig()
	
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
