import constants
import unittest
import util
import plexee
import xbmc
import os
from plex import PlexManager
import time

class plexeeTests(unittest.TestCase):
	"""Tests Plexee functions"""

	if __name__ == '__main__':
		unittest.main()
	
	def setup(self):
		config = mc.GetApp().GetLocalConfig()
		config.SetValue('debug',1)

	def testUsers(self):
		plx = plexee.Plexee()
		plexManager = plx.plexManager
		plexManager.clearMyPlex()
		self.assertTrue(plexManager.myPlexLogin(constants.USERNAME, constants.PASSWORD), 'Login succeeded')
		data, url = plexManager.getLocalUsers()
		users = plx.createUsers(data)
		print('Users: %d' % len(users))
		self.assertNotEqual(0, len(users), "Users set up")

	def testPlexConfig(self):
		#1. Mock Boxee settings file is good
		util.logInfo('#1. Boxee settings file is good')
		tempdir = '__zzz'
		filename = 'registry.xml'
		filepath = os.path.join(os.getcwd(),tempdir)
		fullfilename = os.path.join(filepath,filename)
		os.mkdir(filepath)
		f = open(fullfilename,'w')
		f.write('<registry/>')
		f.close()
		xbmc.setMockProfilePath(filepath)
		config = plexee.PlexeeConfig()
		config.setManualHost('xxx')
		config.setManualHost('yyy')
		config.setManualPort('32400')
		config1 = plexee.PlexeeConfig()
		self.assertEqual('yyy',config1.getManualHost(), 'Use mock Boxee config - Test config reads and writes correctly')

		os.remove(fullfilename)
		time.sleep(2)
		os.rmdir(filepath)
		util.logInfo('#1. END - Boxee settings file is good')

		#2. Mock Boxee file not accessible
		util.logInfo('#2. Mock Boxee file not accessible')
		xbmc.setMockProfilePath('.')
		config = plexee.PlexeeConfig()
		config.setManualHost('zzz')
		config.setDebugOn()
		config1 = plexee.PlexeeConfig()
		self.assertEqual('zzz',config1.getManualHost(), 'Use alternate config - Test config reads and writes correctly')
		util.logInfo('#2. END - Mock Boxee file not accessible')

		#3. Mock Boxee file not accessible, get file again
		util.logInfo('#3. Mock Boxee file not accessible, get file again')
		config = plexee.PlexeeConfig()
		self.assertEqual('zzz',config.getManualHost(), 'Alternate config used again')
		util.logInfo('#3. END - Mock Boxee file not accessible, get file again')





