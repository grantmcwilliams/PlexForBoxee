import mc
import plexee
from plexgdm import PlexGDM
import util
import urllib
import time

def initPlexee():
	manager.clearServers()
	
	#try auto discovery first if set
	if config.GetValue("usediscover"):
		mc.ShowDialogNotification("Auto-discovering Plex Servers...")
		try:
			mc.ShowDialogWait()
			serverList = PlexGDM().getServers();
			if serverList:
				for serverKey in serverList:
					manager.addMyServer(serverList[serverKey]['ip'], serverList[serverKey]['port'])
			else:
				mc.ShowDialogNotification("Failed to find or connect to a Plex Server");
		finally:
			mc.HideDialogWait()
	
	#add manual server
	if config.GetValue("usemanual"):
		host = config.GetValue("manualhost")
		port = config.GetValue("manualport")
		manager.addMyServer(host, port)

	#todo add myPlex
	manager.clearMyPlex()
	if config.GetValue("usemyplex"):
		username = config.GetValue("myplexusername")
		passsword = config.GetValue("myplexpassword")
		if username and passsword:
			manager.myPlexLogin(username, passsword)

def loadHome():
	windowID = getWindowID("home")
	window = activateWindow(windowID)
	
	myLibrary = window.GetList(110)
	sharedLibraries = window.GetList(210)
	myChannels = window.GetList(310)
	myRecentlyAdded = window.GetList(410)

	myLibrary.SetItems(manager.getMyLibrary())
	sharedLibraries.SetItems(manager.getSharedLibraries())
	myChannels.SetItems(manager.getMyChannels())
	myRecentlyAdded.SetItems(manager.getMyRecentlyAdded())
	window.GetControl(1000).SetFocus()

def handleItem(listItem, fromHome = False):
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
		
		# save the state
		if not fromHome:
			mc.GetActiveWindow().PushState()
		
		# secondary items
		if viewGroup == "secondary":
			secondaryListItems = windowInformation.childListItems
			if fromHome:
				handleItem(windowInformation.childListItems[0])
			else:
				#clearItems()
				showWindowInformation(window, windowInformation)
		else:
			# start the new window
			window = activateWindow(nextWindowID)
			showWindowInformation(window, windowInformation)
	
	# Play video
	elif itemType == "Video":
		machineIdentifier = listItem.GetProperty("machineidentifier")
		manager.playVideoUrl(machineIdentifier, url)
		#TEMP DISABLE PLAY WINDOW AND JUST PLAY VIDEO
		#windowInformation = manager.getListItems(machineIdentifier, url)
		#mc.ActivateWindow(PLAY_DIALOG_ID)
		#mc.GetWindow(PLAY_DIALOG_ID).GetList(PLAY_DIALOG_LIST_ID).SetItems(windowInformation.childListItems)
	
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
		mc.GetActiveWidnow().GetList(200).SetItems(mc.ListItems())
	
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
	
	secondaryListItems = None
	manager = plexee.PlexeeManager()
	app = mc.GetApp()
	config = app.GetLocalConfig()

	#default to auto discovery on first launch
	if not config.GetValue("usemanual") and not config.GetValue("usediscover"):
		config.SetValue("usediscover", "1")
	
	#startup
	try:
		mc.ShowDialogWait()
		initPlexee()
		loadHome()
	finally:
		mc.HideDialogWait()
