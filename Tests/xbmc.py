PROFILE_PATH = "C:\Users\Hamish\AppData\Roaming\BOXEE\userdata\profiles\mcneishh"

def setMockProfilePath(path):
	global PROFILE_PATH
	PROFILE_PATH = path

def translatePath(path):
	if path == 'special://profile':
		global PROFILE_PATH
		return PROFILE_PATH
