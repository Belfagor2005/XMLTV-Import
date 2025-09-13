# -*- coding: utf-8 -*-
from xml.etree.cElementTree import iterparse
from calendar import timegm
from time import strptime, struct_time
from . import log

from os.path import exists
from datetime import datetime
from enigma import eServiceReference, eServiceCenter
from re import sub

# mod 20250913 from lululla
UNKNOWN_CHANNELS_FILE = "/etc/epgimport/unknown_channels.txt"


def load_unknown_channels_with_references():
	"""Carica gli unknown channel con i reference trovati"""
	channels = {}
	if exists(UNKNOWN_CHANNELS_FILE):
		try:
			with open(UNKNOWN_CHANNELS_FILE, "r") as f:
				for line in f:
					parts = line.strip().split('|')
					if len(parts) >= 4 and parts[3] == "AUTO":  # Solo quelli con reference trovato
						channel_id = parts[1]
						reference = parts[2]
						channels[channel_id] = reference
		except Exception as e:
			print(f"[EPGImport] Error loading unknown channels with references: {e}", file=log)
	return channels


def getBouquetList(root):
	bouquets = []
	serviceHandler = eServiceCenter.getInstance()
	bouquetlist = serviceHandler.list(root)
	if bouquetlist:
		while True:
			s = bouquetlist.getNext()
			if not s.valid():
				break
			if s.flags & eServiceReference.isDirectory:
				info = serviceHandler.info(s)
				if info:
					bouquets.append((info.getName(s), s))
	return bouquets


def find_channel_reference(channel_id):
	"""Automatically look up the reference for a channel ID"""
	try:
		channel_id = sub(r'\.+', '.', channel_id)
		search_patterns = [
			channel_id,
			channel_id.replace('.', ' '),
			channel_id.replace('_', ' '),
			channel_id.split('.')[0],
		]

		try:
			service_center = eServiceCenter.getInstance()

			bouquet_roots = {
				'tv': eServiceReference('1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "bouquets.tv" ORDER BY bouquet'),
				'radio': eServiceReference('1:7:2:0:0:0:0:0:0:0:0:FROM BOUQUET "bouquets.radio" ORDER BY bouquet')
			}

			for bouquet_type, bouquet_root in bouquet_roots.items():
				bouquets = getBouquetList(bouquet_root)
				for bouquet_name, bouquet_ref in bouquets:
					services = service_center.list(bouquet_ref)
					if services:
						while True:
							service = services.getNext()
							if not service.valid():
								break
							if service.flags & (eServiceReference.isDirectory | eServiceReference.isMarker):
								continue

							# Nome servizio
							info = service_center.info(service)
							service_name = info.getName(service).lower() if info else ""

							for pattern in search_patterns:
								if pattern and pattern in service_name:
									return service.toString()
		except ImportError:
			print("[EPGImport] Cannot import enigma modules for auto-reference search", file=log)

		# Method 2: Search in the lamedb file
		try:
			lamedb_path = "/etc/enigma2/lamedb"
			if exists(lamedb_path):
				with open(lamedb_path, 'r') as f:
					content = f.read().lower()
					# Search for similar channel names
					for pattern in search_patterns:
						if pattern and pattern in content:
							# Extract the reference from the next line
							lines = content.split('\n')
							for i, line in enumerate(lines):
								if pattern in line and i + 1 < len(lines):
									next_line = lines[i + 1].strip()
									if next_line.startswith('1:0:1:'):
										return next_line

		except Exception as e:
			print(f"[EPGImport] Error searching in lamedb: {e}", file=log)

	except Exception as e:
		print(f"[EPGImport] Error in find_channel_reference for {channel_id}: {e}", file=log)

	return None


def save_unknown_channel(channel_id):
	"""Salva gli unknown channel e cerca automaticamente il reference"""
	try:
		# Cerca automaticamente il reference
		channel_reference = find_channel_reference(channel_id)

		with open(UNKNOWN_CHANNELS_FILE, "a") as f:
			timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
			if channel_reference:
				f.write(f"{timestamp}|{channel_id}|{channel_reference}|AUTO\n")
				print(f"[XMLTVConverter] Auto-found reference for {channel_id}: {channel_reference}", file=log)
			else:
				f.write(f"{timestamp}|{channel_id}||NOT_FOUND\n")
				print(f"[XMLTVConverter] Reference not found for: {channel_id}", file=log)
	except Exception as e:
		print(f"[XMLTVConverter] Error saving unknown channel {channel_id}: {e}", file=log)

# mod 20250913 from lululla end


def quickptime(date_str):
	return struct_time(
		(
			int(date_str[0:4]),     # Year
			int(date_str[4:6]),     # Month
			int(date_str[6:8]),     # Day
			int(date_str[8:10]),    # Hour
			int(date_str[10:12]),   # Minute
			0,                      # Second (set to 0)
			-1,                     # Weekday (set to -1 as unknown)
			-1,                     # Julian day (set to -1 as unknown)
			0                       # DST (Daylight Saving Time, set to 0 as unknown)
		)
	)


# fixed Lululla
# 16:15:49.9138 [XMLTVConverter] get_time_utc error:unsupported operand type(s) for //: 'str' and 'int'
def get_time_utc(timestring, fdateparse):
	try:
		values = timestring.split(' ')
		tm = fdateparse(values[0])
		time_gm = timegm(tm)
		if len(values) > 1:
			timezone_offset_str = values[1]  # +0100
			# Extract the numeric part of the time zone
			timezone_offset = int(timezone_offset_str[:3])  # Extract the first 3 characters (+01)
			time_gm -= (timezone_offset * 3600)
		return time_gm
	except Exception as e:
		print(f"[XMLTVConverter] get_time_utc error: {e}")
		return None  # Return None instead of 0 to better handle the error in the calling function


# Preferred language should be configurable, but for now,
# we just like Dutch better!
def get_xml_string(elem, name):
	r = ""
	try:
		for node in elem.findall(name):
			txt = node.text
			lang = node.get("lang", None)
			if not r:
				r = txt
			elif lang == "nl":
				r = txt
	except Exception as e:
		print(f"[XMLTVConverter] get_xml_string error: {e}")
	"""
	# Now returning UTF-8 by default, the epgdat/oudeis must be adjusted to make this work.
	# Note that the default xml.sax.saxutils.unescape() function don't unescape
	# some characters and we have to manually add them to the entities dictionary.
	"""
	"""
	r = unescape(r, entities={
		r"&apos;": r"'",
		r"&quot;": r'"',
		r"&#124;": r"|",
		r"&nbsp;": r" ",
		r"&#91;": r"[",
		r"&#93;": r"]",
	})
	"""
	return r.decode() if isinstance(r, bytes) else r


"""
def get_xml_language(elem, name):
	r = ""
	try:
		for node in elem.findall("lang"):
			for val in node.findall("value"):
				txt = val.text.replace("+", "")
				if not r:
					r = txt
	except Exception as e:
		print("[XMLTVConverter] get_xml_rating_string error:", e)
	return r.decode() if isinstance(r, bytes) else r
"""

""" check if it is possible to insert the language map """


def get_xml_language(elem, name):
	r = ""
	lang_map = {
		"ar": "ara",  # Arabic
		"az": "aze",  # Azerbaijani
		"bg": "bul",  # Bulgarian
		"bn": "ben",  # Bengali
		"bs": "bos",  # Bosnian
		"cs": "ces",  # Czech (ISO 639-2/T), "cze" is bibliographic
		"da": "dan",  # Danish
		"de": "deu",  # German
		"dk": "dan",  # Danish (non standard)
		"el": "gre",  # Greek (bibliographic), "ell" (terminologic ISO 639-2/T)
		"en": "eng",  # English
		"es": "spa",  # Spanish
		"et": "est",  # Estonian
		"fa": "per",  # Persian (bibliographic), "fas" for ISO 639-2/T
		"fi": "fin",  # Finnish
		"fr": "fra",  # French
		"he": "heb",  # Hebrew
		"hi": "hin",  # Hindi
		"hr": "hrv",  # Croatian
		"hu": "hun",  # Hungarian
		"hy": "hye",  # Armenian (ISO 639-2/T), "arm" is bibliographic
		"id": "ind",  # Indonesian
		"is": "isl",  # Icelandic (ISO 639-2/T), "ice" is bibliographic
		"it": "ita",  # Italian
		"ja": "jpn",  # Japanese
		"ka": "kat",  # Georgian (ISO 639-2/T), "geo" is bibliographic
		"ko": "kor",  # Korean
		"lb": "ltz",  # Luxembourgish
		"lt": "lit",  # Lithuanian
		"lv": "lav",  # Latvian
		"mk": "mkd",  # Macedonian (ISO 639-2/T), "mac" is bibliographic
		"ml": "mal",  # Malayalam
		"ms": "msa",  # Malay
		"mt": "mlt",  # Maltese
		"nb": "nob",  # Norwegian Bokmål
		"nl": "nld",  # Dutch (new ISO) - "dut" is old ISO 639-2/B
		"nn": "nno",  # Norwegian Nynorsk
		"no": "nor",  # Norwegian
		"pl": "pol",  # Polish
		"pt": "por",  # Portuguese
		"ro": "ron",  # Romanian (ron is ISO 639-2/T) "rum" is bibliographic
		"ru": "rus",  # Russian
		"se": "sme",  # Northern Sami
		"sk": "slk",  # Slovak (ISO 639-2/T), "slo" is bibliographic
		"sl": "slv",  # Slovenian
		"sq": "sqi",  # Albanian (ISO 639-2/T), "alb" is bibliographic
		"sr": "srp",  # Serbian
		"sv": "swe",  # Swedish
		"ta": "tam",  # Tamil
		"te": "tel",  # Telugu
		"th": "tha",  # Thai
		"tr": "tur",  # Turkish
		"uk": "ukr",  # Ukrainian
		"ur": "urd",  # Urdu
		"vi": "vie",  # Vietnamese
		"zh": "chi",  # Chinese (bibliographic), "zho" for ISO 639-2/T
	}
	try:
		for node in elem.findall(name):
			lang = node.get("lang", None)
			if not r:
				# use mapping dictionary instead of if-elif
				r = lang_map.get(lang, "eng")
	except Exception as e:
		print("[XMLTVConverter] get_xml_string error:{}".format(e))
	return r.decode() if isinstance(r, bytes) else r


def get_xml_rating_string(elem):
	r = ""
	try:
		for node in elem.findall("rating"):
			for val in node.findall("value"):
				txt = val.text.replace("+", "")
				if not r and txt is not None:
					r = txt
	except Exception as e:
		print(f"[XMLTVConverter] get_xml_rating_string error:{e}")
	return r.decode() if isinstance(r, bytes) else r


def enumerateProgrammes(fp):
	"""Enumerates programme ElementTree nodes from file object 'fp'"""
	for event, elem in iterparse(fp):
		try:
			if elem.tag == "programme":
				yield elem
				elem.clear()
			elif elem.tag == "channel":
				# Throw away channel elements, save memory
				elem.clear()
		except Exception as e:
			print(f"[XMLTVConverter] enumerateProgrammes error:{e}")


class XMLTVConverter:
	def __init__(self, channels_dict, category_dict, dateformat="%Y%m%d%H%M%S %Z", offset=0):
		self.channels = channels_dict
		self.categories = category_dict
		if dateformat.startswith("%Y%m%d%H%M%S"):
			self.dateParser = quickptime
		else:
			self.dateParser = lambda x: strptime(x, dateformat)
		self.offset = offset
		print(f"[XMLTVConverter] Using a custom time offset of {offset}")
		
		# Auto-apply fixes from previous runs
		self.apply_auto_fixes()

	def apply_auto_fixes(self):  # # mod 20250913 from lululla
		"""Applica automaticamente i reference trovati in precedenza"""
		auto_fixes = load_unknown_channels_with_references()
		fixes_applied = 0
		
		for channel_id, reference in auto_fixes.items():
			if reference and reference != "NOT_FOUND":
				if channel_id not in self.channels:
					self.channels[channel_id] = []
				if reference not in self.channels[channel_id]:
					self.channels[channel_id].append(reference)
					fixes_applied += 1
					print(f"[XMLTVConverter] Auto-applied fix: {channel_id} -> {reference}", file=log)
		
		if fixes_applied > 0:
			print(f"[XMLTVConverter] Applied {fixes_applied} auto-fixes", file=log)

	"""
		FIXED LULULLA
		self.storage.importEvents(r, (d,))
		SystemError: <built-in function eEPGCache_importEvents> returned a result with an exception set
		TypeError: 'bytes' object cannot be interpreted as an integer
	"""
	"""
	The problem is in the enumFile function, which doesn't handle the stop <= start case correctly.
	Even if the error is detected with the log message, the program is still processed and returned.
	"""

	def enumFile(self, fileobj):  # mod 20250913 from lululla
		print("[XMLTVConverter] Enumerating event information", file=log)
		unknown_channels = set()   # Use set() to avoid duplicates
		already_logged = set()     # To prevent duplicate logs in the same session

		# Nothing to enumerate if no channels are loaded
		if not self.channels:
			return

		for elem in enumerateProgrammes(fileobj):
			channel = elem.get("channel")
			if not channel:
				continue

			channel = channel.lower()

			if channel not in self.channels:
				# Prevent duplicate logs in the same session
				if channel not in already_logged:
					print(f"[XMLTVConverter] Unknown channel: {channel}", file=log)
					already_logged.add(channel)
					# Immediately save the unknown channel with reference search
					save_unknown_channel(channel)

				# Add to the set for final reporting
				unknown_channels.add(channel)

				yield None
				continue

			try:
				services = self.channels[channel]
				start = get_time_utc(elem.get("start"), self.dateParser) + self.offset
				stop = get_time_utc(elem.get("stop"), self.dateParser) + self.offset
				title = get_xml_string(elem, "title")

				if not isinstance(start, int) or not isinstance(stop, int):
					# print(f"[XMLTVConverter] Invalid start/stop time format: start={start}, stop={stop}", file=log)
					print(f"[XMLTVConverter] Skipping event with invalid timing: {title} (start: {elem.get('start')}, stop: {elem.get('stop')})", file=log)
					continue  # Skip this entry if start/stop are not integers

				# Check if stop time is before or equal to start time
				if stop <= start:
					print(f"[XMLTVConverter] Skipping bad start/stop time: {elem.get('start')} ({start}) - {elem.get('stop')} ({stop}) [{title}]", file=log)
					continue  # Skip this entry entirely

				# Check for unrealistic durations (more than 24 hours)
				duration = stop - start
				if duration > 86400:  # 24 hours in seconds
					print(f"[XMLTVConverter] Skipping unrealistic duration: {duration}s for [{title}]", file=log)
					continue  # Skip this entry

				# try/except for EPG XML files with program entries containing <sub-title ... />
				try:
					subtitle = get_xml_string(elem, "sub-title")
				except:
					subtitle = ""

				# try/except for EPG XML files with program entries containing <desc ... />
				try:
					description = get_xml_string(elem, "desc")
				except:
					description = ""
				category = get_xml_string(elem, "category")
				if not category:  # Check if category is empty
					category = "Unknown"  # Assign a default category if empty
				cat_nr = self.get_category(category, duration)
				try:
					rating_str = get_xml_rating_string(elem)
					# hardcode country as ENG since there is no handling for parental certification systems per country yet
					# also we support currently only number like values like "12+" since the epgcache works only with bytes right now
					rating = [("eng", int(rating_str) - 3)]
				except:
					rating = None

				try:  # edit lululla: add map with language
					# hardcode country as ENG since there is no handling for parental certification systems per country yet
					# also we support currently only number like values like "12+" since the epgcache works only with bytes right now
					lang_code = get_xml_language(elem, "title") or get_xml_language(elem, "desc") or "eng"
					language = [(lang_code, int(lang_code) - 3)]
				except:
					language = rating  # or None ???

				# Debugging the types of variables before passing them to yield
				# print(f"[XMLTVConverter] start: {start} (type: {type(start)}), stop: {stop} (type: {type(stop)}), duration: {duration} (type: {type(duration)}), title: {title} (type: {type(title)}), category: {category} (type: {type(category)})", file=log)
				if rating:
					yield (services, (start, stop - start, title, subtitle, description, cat_nr, 0, language))
				else:
					yield (services, (start, stop - start, title, subtitle, description, cat_nr))

			except Exception as e:
				print(f"[XMLTVConverter] parsing event error: {e}")

		if unknown_channels:
			print(f"[XMLTVConverter] Found {len(unknown_channels)} unique unknown channels", file=log)

	# edit for add new category in dictionary
	def get_category(self, cat, duration):
		if not cat or not isinstance(cat, str):
			return 0
		categories = cat.split(',')
		for category in categories:
			category = category.strip()
			category_value = self.categories.get(category)
			if category_value is not None:
				if isinstance(category_value, (tuple, list)) and len(category_value) >= 2:
					if duration > 60 * category_value[1]:
						return category_value[0]
				else:
					return category_value if not isinstance(category_value, (tuple, list)) else category_value[0]
		return 0
