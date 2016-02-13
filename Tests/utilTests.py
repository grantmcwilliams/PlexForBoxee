import unittest
import util

class utilTests(unittest.TestCase):

	if __name__ == '__main__':
		unittest.main()

	
	def testSsl(self):
		http = util.Http()
		data = http.Get('https://wrong.host.badssl.com/')
		print(data)

