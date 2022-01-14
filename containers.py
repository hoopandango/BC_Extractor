from __future__ import annotations

import datetime
from dataclasses import dataclass

from event_data_parsers import UniversalParsers, GatyaParsers, ItemParsers

@dataclass
class Event:
	ID: int = None
	dates: list[datetime.datetime] = None
	versions: tuple[int] = None
	sched: str = None
	sched_data: dict = None
	name: str = None
	text: str = None
	
	def __str__(self) -> str:
		return UniversalParsers.fancyDate(self.dates) + self.name

@dataclass
class EventGroup:
	events: list[Event]
	dates: list[datetime.datetime]
	name: str
	split: bool
	visible: bool
	
	def __str__(self) -> str:
		if self.split:
			if isinstance(self.events[0], Gatya):
				for i in range(len(self.events)-1):
					if self.events[i].dates[1] > self.events[i+1].dates[0]:
						self.events[i].dates[1] = self.events[i+1].dates[0]
			return '\n'.join([str(x) for x in self.events])
		else:
			return UniversalParsers.fancyDate(self.dates) + self.name

@dataclass
class Gatya(Event):
	rates: list[float] = None
	rate_ups: dict[str, int] = None
	diff: list[list[str]] = None
	page: str = None
	slot: int = None
	guarantee: list[bool] = None
	extras: list[str] = None
	exclusives: list[str] = None
	
	def __str__(self):
		self.dates = [self.dates[0], self.dates[-1]]
		return (("%s%s" % GatyaParsers.getString(self)))\
			.format(oldyear=self.dates[0].year, newyear=self.dates[1].year)

@dataclass
class Stage(Event):
	@classmethod
	def fromEvent(cls, e: Event) -> Stage:
		return cls(**e.__dict__)
	
	@classmethod
	def fromItem(cls, i: Item) -> Stage:
		return cls(ID=i.ID, dates=i.dates, versions=i.versions, name=i.name, text=i.text)

@dataclass
class Sale(Event):
	@classmethod
	def fromEvent(cls, e: Event) -> Sale:
		return cls(**e.__dict__)

@dataclass
class Mission(Event):
	@classmethod
	def fromEvent(cls, e: Event) -> Mission:
		return cls(**e.__dict__)

@dataclass
class Item(Event):
	recurring: bool = False
	qty: int = 0
	
	@classmethod
	def fromEvent(cls, e: Event) -> Item:
		return cls(**e.__dict__)
	
	def __str__(self):
		q = (' x ' + str(self.qty)) if self.qty > 1 else ''
		if self.name in ['Cat Food', 'Rare Ticket'] and (self.dates[1] - self.dates[0]).days >= 2:
			q += ' (Daily)' if self.recurring else ' (Only Once)'
		if self.name == 'Rare Ticket':
			q += " - "+self.text
		return ItemParsers.fancyDate(self.dates) + self.name + q

@dataclass
class RawEventGroup(Event):
	IDs: list[int] = None
	
	@classmethod
	def makeSingleton(cls, e: Event) -> RawEventGroup:
		toret: RawEventGroup = RawEventGroup(**e.__dict__)
		toret.IDs = [e.ID]
		return toret
