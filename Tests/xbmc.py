import constants
import platform
import os

PROFILE_PATH = ''

def __getProfilePath():
	"""
	Get platform specific profile path
	Only Windows support has been tested
	"""
	global PROFILE_PATH
	if PROFILE_PATH != '': return PROFILE_PATH
	plat = platform.system()
	path = ''
	if plat == 'Windows' or plat == 'Microsoft':
		path = os.path.join(os.getenv('APPDATA'), 'BOXEE','userdata','profiles',constants.USERNAME)
	elif plat == 'Linux':
		#NOT TESTED
		path = os.path.join('data', '.boxee','UserData','profiles',constants.USERNAME)
	return path

def setMockProfilePath(path):
	global PROFILE_PATH
	PROFILE_PATH = path

def clearMockProfilePath():
	global PROFILE_PATH
	PROFILE_PATH = ''

def translatePath(path):
	if path == 'special://profile':
		return __getProfilePath()
