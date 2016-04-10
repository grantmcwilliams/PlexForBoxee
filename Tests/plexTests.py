import constants
import unittest
import urllib2
import mc
from plex import PlexServer, MyPlexService, PlexManager
from plexee import PlexeeConfig
import util
import time

class plexTests(unittest.TestCase):
	"""Tests the Plex python interface"""

	if __name__ == '__main__':
		unittest.main()
	
	def setup(self):
		config = mc.GetApp().GetLocalConfig()
		config.SetValue('debug','1')

	def testConfigs(self):
		config = mc.GetApp().GetLocalConfig()
		config.SetValue('debug','1')
		config.SetValue('test','fred')
		config.SetValue('test2','1.234')

		config2 = util.Config(PlexeeConfig.getUserSettingsFile())
		config2.SetValue('debug','2')
		self.assertEqual(config2.GetValue('debug'), config.GetValue('debug'))
		self.assertEqual(config2.GetValue('test'), config.GetValue('test'))
		self.assertEqual(config2.GetValue('test2'), config.GetValue('test2'))

	#Server connection settings
	#1. Unencrypted
	#2. Users setup on unencrypted
	#3. Encrypted - no users
	#4. Encrypted - users
	# AND GDM on or off
	# Direct connection or via myPlex

	#Encrypted try ip and bypass certificate?

	def getCurrentDateTime(self):
		return time.strftime("%d/%m/%Y %H:%M:%S")

	def testDirectConnection(self):
		"""Test connect"""
		#self.setup()
		#1. Connect to local plex server
		server = PlexServer.Manual(constants.HOST, constants.PORT)
		server.connect()
		if not server.isTokenRequired:
			self.assertTrue(server.isConnected)
			data, url = server.getLibraryData()
			print(data)
			assert data is not None
		else:
			self.assertFalse(server.isConnected)

		#2. Connect to an invalid server
		server = PlexServer.Manual('10.1.3.1', 32400)
		self.assertFalse(server.isConnected)

		#3. Connect to a non-plex server
		server = PlexServer.Manual('www.google.com', 80)
		self.assertFalse(server.isConnected)


	def testMyPlexConnection(self):
		self.setup()
		print(self.getCurrentDateTime() + "1. Create PlexManager")
		plexManager = PlexManager({
			'platform':'Boxee',
			'platformversion':'System.BuildVersion',
			'provides':'player',
			'product':'Plexee',
			'version':'1.0',
			'device':'Windows',
			'deviceid':'xxx'
		})
		print(self.getCurrentDateTime() + "1. END PlexManager")

		print(self.getCurrentDateTime() + "2. Do Plex Login")
		plexManager.clearMyPlex()
		self.assertTrue(plexManager.myPlexLogin(constants.USERNAME, constants.PASSWORD),'Login succeeded')
		token = plexManager.myplex.authenticationToken
		print('TOKEN: %s' % token)
		assert token is not None
		print(self.getCurrentDateTime() + "2. END Plex Login")

		print(self.getCurrentDateTime() + "3. Connect to server")
		server = PlexServer.Manual(constants.HOST, constants.PORT, token) #token
		server.connect()
		print(self.getCurrentDateTime() + "3. END Connect to server")
		print(self.getCurrentDateTime() + "4. Get data")
		data, url = server.getLibraryData()
		print(data)
		assert data is not None
		print(self.getCurrentDateTime() + "4. END Get data")

	def testMyPlexUsers(self):
		self.setup()
		print(self.getCurrentDateTime() + "1. Create PlexManager")
		plexManager = PlexManager({
			'platform':'Boxee',
			'platformversion':'System.BuildVersion',
			'provides':'player',
			'product':'Plexee',
			'version':'1.0',
			'device':'Windows',
			'deviceid':'xxx'
		})
		print(self.getCurrentDateTime() + "1. END PlexManager")

		print(self.getCurrentDateTime() + "2. Do Plex Login")
		plexManager.clearMyPlex()
		self.assertTrue(plexManager.myPlexLogin(constants.USERNAME, constants.PASSWORD), 'Login succeeded')
		token = plexManager.myplex.authenticationToken
		print('TOKEN: %s' % token)
		assert token is not None
		print(self.getCurrentDateTime() + "2. END Plex Login")
		
		result = plexManager.switchUser('1311516','1399')
		self.assertEqual(result, PlexManager.SUCCESS)
		result = plexManager.switchUser('1311516','139')
		self.assertEqual(result, PlexManager.ERR_USER_PIN_FAILED)
