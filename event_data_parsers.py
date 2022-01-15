import datetime
import json
import string

import numpy as np
import pandas as pd
from local_readers import Readers
from z_downloaders import Downloaders

with open('_config.json') as fl:
	config = json.load(fl)

class UniversalParsers:
	with open(config['outputs']['stages'], encoding='utf-8', newline='') as csvfile:
		autoEventNames = pd.read_csv(csvfile, delimiter='\t', index_col='ID', header=0)
	
	with open("extras\\events.tsv", encoding='utf-8', newline='') as csvfile:
		manualEventNames = pd.read_csv(csvfile, delimiter='\t', index_col='ID', header=0)
		allEventNames = autoEventNames.append(manualEventNames)
	
	@staticmethod
	def fancyDate(datesall: list[datetime.datetime]) -> str:
		toret = "- "
		for dates in zip(datesall[0::2], datesall[1::2]):
			dates = list(dates)
			if (dates[1] - dates[0]).days > 365:  # Forever Events
				toret += f"{dates[0].strftime('%d %b').lstrip('0')}~..."
			elif dates[0].month == dates[1].month:  # Events that don't cross months
				if dates[0].day == dates[1].day:
					# Events that only last one day or less
					toret += dates[0].strftime('%d %b').lstrip('0')
				else:
					toret += '~'.join([dates[0].strftime('%d').lstrip('0'), dates[1].strftime('%d %b').lstrip('0')])
			
			else:  # Events that cross months
				toret += '~'.join([x.strftime('%d %b').lstrip('0') for x in dates])
			
			toret += ', '
		
		return toret[:-2] + ": "
	
	@staticmethod
	def fancyTimes(timesall: list[dict[str, datetime.datetime]]) -> str:
		toret = ""
		if len(timesall) == 0:
			return "All Day"
		for time in timesall:
			if (time['end'].hour == 23 and time['start'].hour == 0):
				return "All Day"
			toret += f"{time['start'].strftime('%I%p').lstrip('0')}~{time['end'].strftime('%I%p').lstrip('0')}"
			toret += ', '
		
		return toret[:-2]
	
	@staticmethod
	def areValidDates(dates: list[datetime.datetime], filters: list[str],
	                  date0: datetime.datetime = datetime.datetime.today()) -> bool:
		if len(filters) > 0:
			if 'N' in filters:  # if event lasts longer than a month or starts after today
				if ((dates[1] - dates[0]).days > 50 and not (dates[0] - date0).days >= 1):
					return False
			elif 'M' in filters:
				if (dates[1] - dates[0]).days > 50:  # If event lasts longer than a month
					return False
			if 'Y' in filters:
				if (date0 - dates[0]).days > -1:  # If event started today or earlier
					return False
		if (date0 - dates[1]).days > 365:  # Default Filter - Ignore (most) discontinued events
			return False
		return True
	
	@classmethod
	def getdates(cls, data: list[str]) -> list[datetime.datetime, datetime.datetime]:
		return [cls.formatDate(data[0] + data[1]), cls.formatDate(data[2] + data[3])-datetime.timedelta(minutes=1)]
	
	@staticmethod
	def getversions(data: list[str]) -> tuple[str, str]:
		return (data[4], data[5])
	
	@staticmethod
	def formatDate(s: str) -> datetime.datetime:
		return datetime.datetime.strptime(s, '%Y%m%d%H%M')
	
	@classmethod
	def getEventName(cls, ID: int, lookup: bool = True) -> str:
		# not used by gatya
		if (18000 <= ID < 18100):
			if (ID == 18000):
				return "Anniversary Slots"
			return "Slots"
		elif (18100 <= ID < 18200):
			return "Scratch Cards Event"
		elif (9000 <= ID < 10000):
			return Readers.getMission(ID)
		
		try:
			name = cls.allEventNames.loc[ID, "name"]
			eng = len([0 for x in name if x in string.ascii_letters])
			full = len([0 for x in name if x.isalpha()])
			if(full < 2*eng):
				if (25000 > ID >= 24000 or 28000 > ID >= 27000):
					name += ' (Baron)'
				return name
		except KeyError:
			pass
		
		if not lookup:
			return 'Unknown'
		
		name = Downloaders.requestStage(ID, 'en')
		if name != 'Unknown':
			# updates name
			cls.autoEventNames.loc[ID, "name"] = name
			
		if (25000 > ID >= 24000 or 28000 > ID >= 27000):
			name += ' (Baron)'
			
		return name
	
	@classmethod
	def updateEventNames(cls):
		with open(config['outputs']['stages'], 'w', encoding='utf-8', newline='') as fil:
			cls.autoEventNames.to_csv(fil, sep='\t', index=True)


class GatyaParsers(UniversalParsers):
	def __init__(self):
		UniversalParsers.__init__(self)
	
	gatyaLocal = pd.read_json(config["outputs"]["gatya_json"], orient='index')
	
	@staticmethod
	def getCategory(banner: list[str]) -> str:
		# tells which category of capsule is in this banner
		p = banner[8]
		if p == "0":
			return "Cat Capsule"  # Normal, lucky, G, catseye, catfruit, etc : uses GatyaDataSetN1.csv
		if p == "1":
			return "Rare Capsule"  # Rare, platinum : uses GatyaDataSetR1.csv
		
		return "Event Capsule"  # bikkuri, etc.
	
	@staticmethod
	def getValueAtOffset(banner: list[str], i: int) -> str:
		slot: int = int(banner[9]) - 1
		# each slot is 15 columns wide
		offset: int = 15 * slot
		return banner[i + offset]
	
	@staticmethod
	def getGatyaRates(banner: list[str]) -> list[int]:
		rates: list[int] = []
		for i in range(5):
			rates.append(int(GatyaParsers.getValueAtOffset(banner, 14 + 2 * i)))  # 14,16,18,20,22
		return rates
	
	@staticmethod
	def getGuarantees(banner: list[str]) -> list[bool]:
		G: list[bool] = []
		for i in range(5):
			G.append(GatyaParsers.getValueAtOffset(banner, 15 + 2 * i) == '1')  # 15,17,19,21,23
		return G
	
	@classmethod
	def appendGatyaLocal(cls, gatya: 'Gatya') -> None:
		toret = {"name": "Unknown", "exclusives": [], "rate_ups": {}, "diff": [[], []]}
		
		if (gatya.page == "Rare Capsule"):
			try:
				obj = cls.gatyaLocal.loc[gatya.ID].to_dict()
				toret["name"] = obj["banner_name"]
				toret["exclusives"] = obj["exclusives"]
				toret["rate_ups"] = obj["rate_ups"]
				toret["diff"] = obj["diff"]
			except KeyError:
				pass
		
		else:
			requested = Downloaders.requestGatya(gatya.ID, 'en', gatya.page)
			if requested == "Unknown":
				requested = gatya.text
			toret["name"] = requested
		
		gatya.name = toret["name"]
		gatya.exclusives = toret["exclusives"]
		gatya.rate_ups = toret["rate_ups"]
		gatya.diff = toret["diff"]
	
	@classmethod
	def getExtras(cls, banner: list[str]) -> list[str]:
		toret = []
		extras = int(cls.getValueAtOffset(banner, 13))
		severID = (extras >> 4) & 1023
		
		if extras & 4:
			toret.append('SU')  # Step-up
		if extras & 16384:
			toret.append('PS')  # Platinum Shard
		
		if not extras & 8:
			return toret  # No item drops
		# if it has item drops:
		item = Readers.getItemBySever(severID)
		if item == 'Lucky Ticket':
			toret.append('L')  # Has lucky ticket
		return toret
	
	@staticmethod
	def getString(banner: 'Gatya') -> tuple[str, str]:
		# tuple (datestring, reststring)
		bonuses: list[str] = []
		
		if banner.guarantee[3] == 1:  bonuses.append('G')
		bonuses.extend(banner.extras)
		bonuses.extend([x for x in banner.exclusives if x != 'D'])
		bonusesStr: str = f" [{'/'.join(bonuses)}]" if len(bonuses) > 0 else ''
		
		diff: str = f' (+ {", ".join(banner.diff[0])})' if 5 > len(banner.diff[0]) > 0 else ''
		
		rate_ups: str = " {{" + ", ".join([f"{K}x rate on {', '.join(V)}" for (K, V) in banner.rate_ups.items()]) + "}}" \
			if len(banner.rate_ups) > 0 else ''
		
		name = banner.name if banner.name != 'Unknown' else banner.text
		return (GatyaParsers.fancyDate(banner.dates), '%s%s%s%s' % (name, bonusesStr, diff, rate_ups))

class StageParsers(UniversalParsers):
	def __init__(self):
		UniversalParsers.__init__(self)
	
	@staticmethod
	def formatTime(t: str) -> datetime.time:
		if t == "2400":
			t = "2359"
		if t == "0":
			t = "0000"
		if len(t) == 3:  # fixes time if hour is < 10am
			t = '0' + t
		dt = datetime.datetime.strptime(t, '%H%M')
		return datetime.time(dt.hour, dt.minute)
	
	@staticmethod
	def formatMDHM(s: str, t: str) -> datetime.datetime:
		if t == "2400":
			t = "2359"
		if t == "0":
			t = "0000"
		if len(s) == 3:  # fixes date if month isn't nov or dec
			s = '0' + s
		
		return datetime.datetime.strptime(s + t, '%m%d%H%M')
	
	@staticmethod
	def binaryweekday(N: int) -> list[bool]:
		list_to_return: list[bool] = [bool(int(x)) for x in list(bin(N))[2:][::-1]]
		while len(list_to_return) < 7:
			list_to_return.append(False)
		return list_to_return
	
	@classmethod
	def yearly(cls, data: list[str]) -> tuple[list[dict[str, list[dict[str, datetime.datetime]]]], list[int]]:
		numberOfPeriods: int = int(data[7])
		n: int = 8
		output: list[dict[str, list[dict[str, datetime.datetime]]]] = [dict() for _ in range(numberOfPeriods)]
		IDs: list[int] = []
		for i in range(numberOfPeriods):
			
			times, n = int(data[n]), n + 1
			output[i]["times"] = [dict() for _ in range(times)]
			
			for j in range(times):
				startDate, n = data[n], n + 1
				startTime, n = data[n], n + 1
				endDate, n = data[n], n + 1
				endTime, n = data[n], n + 1
				output[i]["times"][j]["start"] = cls.formatMDHM(startDate, startTime)
				output[i]["times"][j]["end"] = cls.formatMDHM(endDate, endTime)
				if output[i]["times"][j]["end"] < output[i]["times"][j]["start"]:
					# this means the event ends the next year, like it starts on christmas and lasts for 2 weeks
					output[i]["times"][j]["end"] = output[i]["times"][j]["end"].replace(year=1901)
			
			n = n + 3  # trailing zeros
		
		nIDs, n = int(data[n]), n + 1
		for k in range(max(nIDs, 1)):
			ID, n = int(data[n]), n + 1
			if nIDs > 0:
				IDs.append(ID)
		
		return output, IDs
	
	@classmethod
	def monthly(cls, data: list[str]) -> tuple[list[dict[str, list[int | dict[str, datetime.datetime]]]], list[int]]:
		numberOfPeriods: int = int(data[7])
		n: int = 9
		output: list[dict[str, list[int | dict[str, datetime.time]]]] = [dict() for _ in range(numberOfPeriods)]
		IDs = []
		for i in range(numberOfPeriods):
			
			dates, n = int(data[n]), n + 1
			output[i]["dates"] = [-1] * dates
			for u in range(int(dates)):
				output[i]["dates"][u], n = int(data[n]), n + 1
			
			n = n + 1  # Trailing zero
			
			times, n = int(data[n]), n + 1
			output[i]["times"] = [dict() for _ in range(times)]
			
			for j in range(times):
				start, n = data[n], n + 1
				end, n = data[n], n + 1
				output[i]["times"][j]["start"] = cls.formatTime(start)
				output[i]["times"][j]["end"] = cls.formatTime(end)
			
			nIDs, n = int(data[n]), n + 1
			for k in range(nIDs):
				ID, n = int(data[n]), n + 1
				if nIDs > 0:
					IDs.append(ID)
		
		return output, IDs
	
	@classmethod
	def weekly(cls, data: list[str]) -> tuple[list[dict[str, list[int | dict[str, datetime.time]]]], list[int]]:
		numberOfPeriods: int = int(data[7])
		n: int = 10
		output: list[dict[str, list[int | dict[str, datetime.time]]]] = [dict() for _ in range(numberOfPeriods)]
		IDs: list[int] = []
		for i in range(numberOfPeriods):
			
			weekdays, n = cls.binaryweekday(int(data[n])), n + 1
			output[i]["weekdays"] = weekdays
			times, n = int(data[n]), n + 1
			output[i]["times"] = [dict() for _ in range(times)]
			
			for j in range(times):
				start, n = data[n], n + 1
				end, n = data[n], n + 1
				output[i]["times"][j]["start"] = cls.formatTime(start)
				output[i]["times"][j]["end"] = cls.formatTime(end)
			
			nIDs, n = int(data[n]), n + 1
			
			for k in range(max(nIDs, 1)):
				ID, n = int(data[n]), n + 1
				if nIDs > 0:
					IDs.append(ID)
		
		return output, IDs
	
	@classmethod
	def daily(cls, data: list[str]) -> tuple[list[dict[str, list[dict[str, datetime.time]]]], list[int]]:
		numberOfPeriods: int = int(data[7])
		n: int = 11
		output: list[dict[str, list[dict[str, datetime.time]]]] = [dict() for _ in range(numberOfPeriods)]
		IDs = []
		for i in range(numberOfPeriods):
			
			times, n = int(data[n]), n + 1
			output[i]["times"] = [dict() for _ in range(times)]
			
			for j in range(times):
				startTime, n = data[n], n + 1
				endTime, n = data[n], n + 1
				output[i]["times"][j]["start"] = cls.formatTime(startTime)
				output[i]["times"][j]["end"] = cls.formatTime(endTime)
		
		nIDs, n = int(data[n]), n + 1
		for k in range(max(nIDs, 1)):
			ID, n = int(data[n]), n + 1
			if nIDs > 0:
				IDs.append(ID)
		
		return output, IDs
	
	@staticmethod
	def interpretDates(dates: np.array) -> tuple[int, int, int]:
		# takes in dates array and the number of days in the month in which they start
		# returns a 3-tuple -> (group_size, starting_date, ending_date)
		if len(dates) <= 4:  # don't group these
			return (0, 0, 0)
		diffs = list(np.diff(dates))
		mode = max(set(diffs), key=diffs.count)
		outliers = [i for i, x in enumerate(diffs) if x != mode]
		if len(outliers) > 1:
			# there can be at most one gap in any patterned data
			return (0, 0, 0)
		elif len(outliers) == 0:
			# there is no gap, assume all events to be happening in the same month
			return (mode, min(dates), max(dates))
		else:
			# there is a gap, repetition started after it and ended at it
			# a better algorithm would check whether or not there is an actual rollover
			# taking in the number of days in the month as a parameter
			return (mode, dates[outliers[0] + 1], dates[outliers[0]])
		# this algorithm ignores month rollover diff [-1->0], and can give false positives, but they are not expected

class ItemParsers(UniversalParsers):
	def __init__(self):
		UniversalParsers.__init__(self)

class MissionParsers(UniversalParsers):
	def __init__(self):
		UniversalParsers.__init__(self)
