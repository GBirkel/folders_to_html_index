import os, sys
import xml.dom.minidom
from datetime import datetime, timezone


# Read in the standard configuration file and return its parsed contents
def read_config():
	config = {}
	if os.access("config.xml", os.F_OK):
		config_xml = xml.dom.minidom.parse("config.xml")
		root_el = config_xml.documentElement
		config['installpath'] = root_el.getElementsByTagName("installpath")[0].firstChild.data
		paths_el = root_el.getElementsByTagName("cardpaths")[0]
		paths = []
		for item in paths_el.childNodes:
			if item.nodeType == item.ELEMENT_NODE:
				paths.append(item.firstChild.data)
		config['paths'] = paths
		return config
	else:
		return None


def get_folders_and_files(dirname):
	folders = []
	files = []
	for f in os.scandir(dirname):
		if not os.path.islink(f):	# Important! Don't want to go down a link rabbit hole!
			if f.is_dir():
				folders.append(f)
			if f.is_file():
				files.append(f)
	return (folders, files)


# Support function to pretty-print dates that datetime can't handle
def pretty_datetime(unix_time):
	t = datetime.fromtimestamp(unix_time, timezone.utc)	
	# Code loosely adapted from Perl's HTTP-Date
	MoY = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
	mon = t.month - 1
	date_str = '%04d-%s-%02d' % (t.year, MoY[mon], t.day)
	hour = t.hour
	half_day = 'am'
	if hour > 11:
		half_day = 'pm'
	if hour > 12:
		hour = hour - 12
	elif hour == 0:
		hour = 12
	u = t.tzname()
	u_str = ''
	if u is not None:
		u_str = ' ' + u
	time_str = '%02d:%02d%s' % (hour, t.minute, half_day)

	return date_str + ' ' + time_str + u_str


# Support function to pretty-print file sizes
def pretty_size(s):
	if s > (1000 * 1000 * 1000):
		return ("%.2f gb" % (s / (1000 * 1000 * 1000)))
	elif s > (1000 * 1000):
		return ("%.2f mb" % (s / (1000 * 1000)))
	elif s > 1000:
		return ("%.2f kb" % (s / 1000))
	else:
		return ("%s b" % s)


if __name__ == "__main__":
   sys.exit()
