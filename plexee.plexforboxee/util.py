import mc
import datetime

def cleanString(string):
	return string.encode("utf-8", "replace")

def getResolution(mediaNode):
	resolution = mediaNode.attrib.get("videoResolution","")
	if resolution.isdigit():
		resolution = resolution + "p"
	else:
		resolution = resolution.upper()
	return cleanString(resolution)
	
def msToResumeTime(ms):
	if ms == 0:
		return "0 sec"
		
	s = int(int(ms)/1000)
	m = 0
	h = 0
	f = ""
	if s>=60:
		m=int(s/60)
	if m>=60:
		h=int(m/60)
		f = str(h) + " hr "
	s=s-m*60
	m=m-h*60
	if m>0:
		f = f + str(m) + " min "
	if s>0:
		f = f + str(s) + " sec "
	return f
	
def msToFormattedDuration(ms, humanReadable = True):
	td = datetime.timedelta(milliseconds=ms)
	td = td - datetime.timedelta(microseconds=td.microseconds)
	durParts = str(td).split(':')

	duration = ""
	if humanReadable:
		if durParts[0] != "0":
			duration = durParts[0] + " hr "
		if durParts[1] != "0":
			duration = duration + durParts[1] + " min"
		if duration == "" and durParts[2] != "0":
			duration = durParts[2] + " sec"
	else:
		if durParts[0] != "0":
			duration = durParts[0] + ":"
		duration = duration + durParts[1].rjust(2,'0')+':'+durParts[2].rjust(2,'0')
	return duration

def logDebug(msg):
	_debug = mc.GetApp().GetLocalConfig().GetValue("debug")
#	msg = cleanString(msg)
	if _debug:
		try:
			print "Plexee: " + msg
		except:
			pass
	else:
		mc.LogDebug("Plexee: " + msg)

def logInfo(msg):
#	msg = cleanString(msg)
	mc.LogInfo("Plexee: "+msg)
	
def logError(msg):
#	msg = cleanString(msg)
	mc.LogError("Plexee: "+msg)

def formatEpisodeTitle(season, episode, title):
	if season == "":
		return 'E%s - %s' % (str(episode), title)
	else:
		return 'S%s:E%s - %s' % (str(season), str(episode), title)

def getIndex(listItem, list):
	result = -1
	for l in list:
		result = result + 1
		if l.GetProperty('key') == listItem.GetProperty('key'):
			return result
	return result

	