import mc
import datetime

def cleanString(string):
	return string.encode("utf-8", "replace")
	
def msToFormattedDuration(ms):
	td = datetime.timedelta(milliseconds=ms)
	td = td - datetime.timedelta(microseconds=td.microseconds)
	durParts = str(td).split(':')

	duration = ""
	if durParts[0] != "0":
		duration = durParts[0] + " hr "
	if durParts[1] != "0":
		duration = duration + durParts[1] + " min"
	if duration == "" and durParts[2] != "0":
		duration = durParts[2] + " sec"
	return duration

def logDebug(msg):
	_debug = mc.GetApp().GetLocalConfig().GetValue("debug")
	if _debug:
		print "Plexee: "+msg
	else:
		mc.LogDebug("Plexee: "+msg)

def logInfo(msg):
	mc.LogInfo("Plexee: "+msg)
	
def logError(msg):
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