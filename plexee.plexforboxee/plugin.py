import mc
from plexee import Plexee, PlexeeSettingsDialog, PlexeeConfig, PlexeeConnectionDialog, PlexeePlayDialog

# ENTRY POINT ##################################################################
if ( __name__ == "__main__" ):
	plexee = Plexee()
	config = plexee.config
	
	#Jinxo: Set debug on to get all debug messages
	#config.SetValue("debug", "1")
	
	#default to autodiscover on first start of application
	if not config.isManualConnectOn() and not config.isAutoConnectOn() and not config.isMyPlexConnectOn():
		config.setAutoConnectOn()

	config.setHasStarted(False)
	config.setLastSearch("")
	
	#startup - sets the exit screen as the first screen in the stack - which means on exiting the home screen
	#it pops up.
	#plexee.getExitWindow().activate()
	mc.ActivateWindow(Plexee.DIALOG_EXIT_ID)
	
