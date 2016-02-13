import sys
import struct
import time
import util
import urllib2, socket

##
#Implements the Plex G'day Mate service
#Borrowed from PlexAPI.py at:
#https://github.com/iBaa/PlexConnect
class PlexGDM:

	def __init__(self):
		self.IP_PlexGDM = '<broadcast>'
		#self.IP_PlexGDM = '239.0.0.250'
		self.Port_PlexGDM = 32414
		self.Msg_PlexGDM = 'M-SEARCH * HTTP/1.0'

	##
	#	Returns a list of the plex.PlexServer's found
	#
	def getServers(self, timeoutsec):
		util.logDebug("***")
		util.logDebug("Looking up Plex Media Server")
		util.logDebug("***")
		
		# setup socket for discovery -> multicast message
		GDM = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		GDM.settimeout(timeoutsec)
		
		# Set the time-to-live for messages to 1 for local network
		GDM.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
		
		returnData = []
		try:
			# Send data to the multicast group
			util.logDebug("Sending discovery message: %s" % self.Msg_PlexGDM)
			GDM.sendto(self.Msg_PlexGDM, (self.IP_PlexGDM, self.Port_PlexGDM))

			# Look for responses from all recipients
			while True:
				try:
					data, server = GDM.recvfrom(1024)
					returnData.append( { 'from' : server,
										 'data' : data } )
				except socket.timeout:
					break
		finally:
			GDM.close()

		discovery_complete = True

		PMS_list = {}
		if returnData:
			for response in returnData:
				update = { 'ip' : response.get('from')[0] }
				
				# Check if we had a positive HTTP response						  
				if "200 OK" in response.get('data'):
					for each in response.get('data').split('\n'): 
						# decode response data
						update['discovery'] = "auto"
						#update['owned']='1'
						#update['master']= 1
						#update['role']='master'
						
						if "Content-Type:" in each:
							update['content-type'] = each.split(':')[1].strip()
						elif "Resource-Identifier:" in each:
							update['uuid'] = each.split(':')[1].strip()
						elif "Name:" in each:
							update['serverName'] = each.split(':')[1].strip().decode('utf-8', 'replace')  # store in utf-8
						elif "Port:" in each:
							update['port'] = each.split(':')[1].strip()
						elif "Updated-At:" in each:
							update['updated'] = each.split(':')[1].strip()
						elif "Version:" in each:
							update['version'] = each.split(':')[1].strip()
						
				PMS_list[update['uuid']] = update
		
		if PMS_list=={}:
			util.logDebug("GDM: No servers discovered")
		else:
			util.logDebug("GDM: Servers discovered: %d" % len(PMS_list))
			for uuid in PMS_list:
				msg = "%s %s:%s" % (PMS_list[uuid]['serverName'], PMS_list[uuid]['ip'], PMS_list[uuid]['port'])
				util.logDebug(msg)
		
		return PMS_list
		